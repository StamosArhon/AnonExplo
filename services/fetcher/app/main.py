import ipaddress
import re
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "backend",
    "fetcher",
    "search-provider",
    "model-backend",
    "host.docker.internal",
}


class FetcherError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "fetch_failed",
        status_code: int = 400,
        upstream_status: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.upstream_status = upstream_status
        self.retryable = retryable

    def to_detail(self) -> dict[str, str | int | bool | None]:
        return {
            "message": self.message,
            "code": self.code,
            "upstream_status": self.upstream_status,
            "retryable": self.retryable,
        }


class Settings(BaseSettings):
    fetcher_host: str = Field(default="0.0.0.0", validation_alias="FETCHER_HOST")
    fetcher_port: int = Field(default=8081, validation_alias="FETCHER_PORT")
    fetch_request_timeout_seconds: float = Field(
        default=20.0,
        validation_alias="FETCH_REQUEST_TIMEOUT_SECONDS",
    )
    fetch_max_response_bytes: int = Field(
        default=2_000_000,
        validation_alias="FETCH_MAX_RESPONSE_BYTES",
    )
    fetch_max_text_chars: int = Field(default=40_000, validation_alias="FETCH_MAX_TEXT_CHARS")
    fetch_min_content_chars: int = Field(default=200, validation_alias="FETCH_MIN_CONTENT_CHARS")
    fetch_min_word_count: int = Field(default=40, validation_alias="FETCH_MIN_WORD_COUNT")
    fetch_user_agent: str = Field(
        default="AnonExploFetcher/0.1 (local self-hosted use)",
        validation_alias="FETCH_USER_AGENT",
    )
    fetch_accept_language: str = Field(
        default="en-US,en;q=0.7",
        validation_alias="FETCH_ACCEPT_LANGUAGE",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


class FetchRequest(BaseModel):
    url: str = Field(min_length=1)


class FetchResponse(BaseModel):
    requested_url: str
    final_url: str
    title: str | None = None
    excerpt: str
    content_text: str
    content_char_count: int = 0
    word_count: int = 0
    content_type: str | None = None
    retrieval_method: str = "direct_html"
    content_quality: str = "usable"
    warnings: list[str] = Field(default_factory=list)


def validate_requested_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FetcherError("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise FetcherError("URL is missing a hostname.")

    hostname = parsed.hostname.lower()
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".local"):
        raise FetcherError("Refusing to fetch localhost or internal hostnames.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
    ):
        raise FetcherError("Refusing to fetch private or reserved IP ranges.")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _classify_content_quality(
    content_text: str,
    word_count: int,
    settings: Settings,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if len(content_text) < settings.fetch_min_content_chars or word_count < settings.fetch_min_word_count:
        warnings.append(
            "Extracted page content looks thin and may be a paywall shell, blocked document, or non-readable layout."
        )
        return "thin", warnings

    return "usable", warnings


def extract_document(
    html: str,
    source_url: str,
    settings: Settings,
    *,
    retrieval_method: str = "direct_html",
) -> dict[str, str | int | list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "nav", "form", "aside", "footer", "header"]):
        tag.decompose()

    title = None
    if soup.title and soup.title.string:
        title = normalize_text(soup.title.string)

    root = soup.find("article") or soup.find("main") or soup.body or soup
    text_blocks: list[str] = []
    for node in root.find_all(["p", "li", "blockquote", "h1", "h2", "h3"]):
        text = normalize_text(node.get_text(" ", strip=True))
        if text and text not in text_blocks:
            text_blocks.append(text)

    if not text_blocks:
        fallback = normalize_text(root.get_text(" ", strip=True))
        if fallback:
            text_blocks.append(fallback)

    content_text = "\n\n".join(text_blocks)[: settings.fetch_max_text_chars]
    content_char_count = len(content_text)
    word_count = len([word for word in content_text.split(" ") if word])
    content_quality, warnings = _classify_content_quality(content_text, word_count, settings)
    excerpt = content_text[:400]
    return {
        "requested_url": source_url,
        "final_url": source_url,
        "title": title or "",
        "excerpt": excerpt,
        "content_text": content_text,
        "content_char_count": content_char_count,
        "word_count": word_count,
        "content_type": "text/html",
        "retrieval_method": retrieval_method,
        "content_quality": content_quality,
        "warnings": warnings,
    }


async def _raise_for_upstream_failure(response: httpx.Response) -> None:
    preview_bytes = await response.aread()
    preview_text = preview_bytes[:300].decode("utf-8", errors="replace")
    normalized_preview = normalize_text(preview_text).lower()

    if response.status_code in {403, 429} and "robot policy" in normalized_preview:
        raise FetcherError(
            "Remote site denied automated fetching under its robot policy.",
            code="blocked_by_remote_policy",
            status_code=502,
            upstream_status=response.status_code,
            retryable=False,
        )

    if response.status_code == 403:
        raise FetcherError(
            "Remote site denied the fetch request.",
            code="upstream_forbidden",
            status_code=502,
            upstream_status=response.status_code,
            retryable=False,
        )

    if response.status_code == 429:
        raise FetcherError(
            "Remote site rate-limited the fetch request.",
            code="upstream_rate_limited",
            status_code=502,
            upstream_status=response.status_code,
            retryable=True,
        )

    if 500 <= response.status_code <= 599:
        raise FetcherError(
            f"Remote site returned {response.status_code}.",
            code="upstream_server_error",
            status_code=502,
            upstream_status=response.status_code,
            retryable=True,
        )

    raise FetcherError(
        f"Remote site returned {response.status_code}.",
        code="upstream_http_error",
        status_code=502,
        upstream_status=response.status_code,
        retryable=False,
    )


async def fetch_html(url: str, settings: Settings) -> dict[str, str | int | list[str]]:
    headers = {
        "User-Agent": settings.fetch_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": settings.fetch_accept_language,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
    }
    timeout = httpx.Timeout(settings.fetch_request_timeout_seconds)

    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            if response.status_code >= 400:
                await _raise_for_upstream_failure(response)

            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise FetcherError(
                    "Only HTML pages are supported by the fetch pipeline.",
                    code="unsupported_content_type",
                    status_code=400,
                    upstream_status=response.status_code,
                    retryable=False,
                )

            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > settings.fetch_max_response_bytes:
                    raise FetcherError(
                        "Fetched page exceeded the configured size limit.",
                        code="response_too_large",
                        status_code=400,
                        upstream_status=response.status_code,
                        retryable=False,
                    )

    html = chunks.decode("utf-8", errors="replace")
    document = extract_document(
        html,
        url,
        settings,
        retrieval_method="direct_html",
    )
    document["final_url"] = str(response.url)
    document["content_type"] = content_type
    return document


app = FastAPI(title="AnonExplo Fetcher", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/fetch")
async def fetch(
    payload: FetchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FetchResponse:
    try:
        validate_requested_url(payload.url)
        document = await fetch_html(payload.url, settings)
        return FetchResponse.model_validate(document)
    except FetcherError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream returned {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {exc}") from exc
