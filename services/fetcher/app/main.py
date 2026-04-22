import ipaddress
import re
from functools import lru_cache
from typing import Annotated
from urllib.parse import parse_qs, quote, unquote, urlparse

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

WIKIMEDIA_HOST_SUFFIXES = (
    "wikipedia.org",
    "wiktionary.org",
    "wikibooks.org",
    "wikiquote.org",
    "wikinews.org",
    "wikisource.org",
    "wikiversity.org",
    "wikivoyage.org",
    "wikimedia.org",
    "mediawiki.org",
)


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
    fetch_wikimedia_api_enabled: bool = Field(
        default=False,
        validation_alias="FETCH_WIKIMEDIA_API_ENABLED",
    )
    fetch_wikimedia_api_user_agent: str = Field(
        default="",
        validation_alias="FETCH_WIKIMEDIA_API_USER_AGENT",
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


def describe_exception_message(exc: Exception) -> str:
    message = normalize_text(str(exc))
    return message or exc.__class__.__name__


def build_transport_fetch_error(
    exc: httpx.HTTPError,
    *,
    source_label: str = "Remote site",
    timeout_code: str = "upstream_timeout",
    transport_code: str = "upstream_transport_error",
) -> FetcherError:
    if isinstance(exc, httpx.TimeoutException):
        return FetcherError(
            f"{source_label} timed out before the fetch completed.",
            code=timeout_code,
            status_code=502,
            retryable=True,
        )

    return FetcherError(
        f"{source_label} transport error: {describe_exception_message(exc)}.",
        code=transport_code,
        status_code=502,
        retryable=True,
    )


def _is_wikimedia_hostname(hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.lower()
    return any(normalized == suffix or normalized.endswith(f".{suffix}") for suffix in WIKIMEDIA_HOST_SUFFIXES)


def extract_wikimedia_page_title(url: str) -> str | None:
    parsed = urlparse(url)
    if not _is_wikimedia_hostname(parsed.hostname):
        return None

    raw_title: str | None = None
    if parsed.path.startswith("/wiki/"):
        raw_title = parsed.path.removeprefix("/wiki/")
    elif parsed.path.endswith("/index.php"):
        raw_title = parse_qs(parsed.query).get("title", [None])[0]

    if not raw_title:
        return None

    normalized_title = normalize_text(unquote(raw_title).replace("_", " "))
    if not normalized_title or normalized_title.lower().startswith("special:"):
        return None
    return normalized_title


def _build_wikimedia_article_url(source_url: str, page_title: str) -> str:
    parsed = urlparse(source_url)
    normalized_title = page_title.replace(" ", "_")
    encoded_title = quote(normalized_title, safe=":")
    return f"{parsed.scheme}://{parsed.netloc}/wiki/{encoded_title}"


def _normalize_display_title(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    soup = BeautifulSoup(value, "html.parser")
    text = normalize_text(soup.get_text(" ", strip=True))
    return text or fallback


def _build_wikimedia_api_user_agent(settings: Settings) -> str:
    agent = settings.fetch_wikimedia_api_user_agent.strip()
    if agent:
        return agent

    raise FetcherError(
        "Wikimedia API access is enabled, but FETCH_WIKIMEDIA_API_USER_AGENT is not configured.",
        code="wikimedia_api_user_agent_required",
        status_code=500,
        retryable=False,
    )


def should_use_wikimedia_api(url: str, settings: Settings) -> bool:
    if not settings.fetch_wikimedia_api_enabled:
        return False
    return extract_wikimedia_page_title(url) is not None


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


def build_bounded_content_text(
    text_blocks: list[str],
    max_chars: int,
) -> tuple[str, list[str]]:
    joined_text = "\n\n".join(text_blocks)
    if len(joined_text) <= max_chars:
        return joined_text, []

    if not text_blocks:
        return "", []

    separator = "\n\n...\n\n"
    head_budget = max(0, min(max_chars - len(separator), int(max_chars * 0.55)))
    tail_budget = max(0, max_chars - len(separator) - head_budget)

    head_blocks: list[str] = []
    used_head = 0
    head_index = -1
    for index, block in enumerate(text_blocks):
        block_cost = len(block) + (2 if head_blocks else 0)
        if head_blocks and used_head + block_cost > head_budget:
            break
        if not head_blocks and len(block) > head_budget and head_budget > 0:
            head_blocks.append(block[:head_budget].rstrip())
            used_head = len(head_blocks[0])
            head_index = index
            break
        if used_head + block_cost > max_chars:
            break
        head_blocks.append(block)
        used_head += block_cost
        head_index = index

    tail_blocks: list[str] = []
    used_tail = 0
    for index in range(len(text_blocks) - 1, head_index, -1):
        block = text_blocks[index]
        block_cost = len(block) + (2 if tail_blocks else 0)
        if tail_blocks and used_tail + block_cost > tail_budget:
            break
        if not tail_blocks and len(block) > tail_budget and tail_budget > 0:
            tail_blocks.append(block[-tail_budget:].lstrip())
            used_tail = len(tail_blocks[0])
            break
        if used_tail + block_cost > max_chars:
            break
        tail_blocks.append(block)
        used_tail += block_cost

    tail_blocks.reverse()
    if not tail_blocks or head_index >= len(text_blocks) - len(tail_blocks) - 1:
        return joined_text[:max_chars], [
            "Extracted text was truncated to the configured text-character limit; middle or trailing sections may be missing."
        ]

    bounded_text = "\n\n".join(head_blocks) + separator + "\n\n".join(tail_blocks)
    return bounded_text[:max_chars], [
        "Extracted text was truncated to the configured text-character limit using head-and-tail retention; middle sections may be missing."
    ]


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

    content_text, truncation_warnings = build_bounded_content_text(
        text_blocks,
        settings.fetch_max_text_chars,
    )
    content_char_count = len(content_text)
    word_count = len([word for word in content_text.split(" ") if word])
    content_quality, warnings = _classify_content_quality(content_text, word_count, settings)
    warnings = [*warnings, *truncation_warnings]
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


def build_extracted_document(
    html_bytes: bytes,
    *,
    source_url: str,
    final_url: str,
    content_type: str,
    settings: Settings,
    retrieval_method: str,
    warnings: list[str] | None = None,
) -> dict[str, str | int | list[str]]:
    html = html_bytes.decode("utf-8", errors="replace")
    document = extract_document(
        html,
        source_url,
        settings,
        retrieval_method=retrieval_method,
    )
    document["final_url"] = final_url
    document["content_type"] = content_type
    if warnings:
        document["warnings"] = [*document["warnings"], *warnings]
    return document


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

    chunks = bytearray()
    content_type = ""
    final_url = url
    retrieval_method = "direct_html"
    partial_warnings: list[str] = []

    try:
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

                final_url = str(response.url)
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > settings.fetch_max_response_bytes:
                        del chunks[settings.fetch_max_response_bytes :]
                        retrieval_method = "direct_html_partial"
                        partial_warnings.append(
                            "Source HTML was truncated at the configured response-size limit; later page sections may be missing."
                        )
                        break
    except httpx.HTTPError as exc:
        if chunks:
            retrieval_method = "direct_html_partial"
            partial_warnings.append(
                f"Source HTML stream ended early because of a transport error ({describe_exception_message(exc)}); extracted text may be incomplete."
            )
        else:
            raise build_transport_fetch_error(exc) from exc

    return build_extracted_document(
        bytes(chunks),
        source_url=url,
        final_url=final_url,
        content_type=content_type or "text/html",
        settings=settings,
        retrieval_method=retrieval_method,
        warnings=partial_warnings,
    )


async def fetch_wikimedia_api_document(url: str, settings: Settings) -> dict[str, str | int | list[str]]:
    page_title = extract_wikimedia_page_title(url)
    if not page_title:
        raise FetcherError(
            "Wikimedia API access requires a supported Wikimedia article URL.",
            code="wikimedia_unsupported_url",
            status_code=400,
            retryable=False,
        )

    parsed = urlparse(url)
    api_url = f"{parsed.scheme}://{parsed.netloc}/w/api.php"
    user_agent = _build_wikimedia_api_user_agent(settings)
    headers = {
        "User-Agent": user_agent,
        "Api-User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": settings.fetch_accept_language,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
    }
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "text|displaytitle",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
        "disablelimitreport": "1",
        "disableeditsection": "1",
        "disabletoc": "1",
    }
    timeout = httpx.Timeout(settings.fetch_request_timeout_seconds)

    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
            response = await client.get(api_url, params=params)
            if response.status_code >= 400:
                await _raise_for_upstream_failure(response)
    except httpx.HTTPError as exc:
        raise build_transport_fetch_error(
            exc,
            source_label="Wikimedia API",
            timeout_code="wikimedia_api_timeout",
            transport_code="wikimedia_api_transport_error",
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise FetcherError(
            f"Wikimedia API returned invalid JSON: {exc}",
            code="wikimedia_api_invalid_response",
            status_code=502,
            upstream_status=response.status_code,
            retryable=False,
        ) from exc

    error_payload = payload.get("error")
    if isinstance(error_payload, dict):
        error_message = error_payload.get("info") or error_payload.get("code") or "unknown parse error"
        raise FetcherError(
            f"Wikimedia API could not parse the requested page: {error_message}.",
            code="wikimedia_api_parse_error",
            status_code=502,
            upstream_status=response.status_code,
            retryable=False,
        )

    parse_payload = payload.get("parse")
    if not isinstance(parse_payload, dict):
        raise FetcherError(
            "Wikimedia API returned an unexpected payload.",
            code="wikimedia_api_invalid_response",
            status_code=502,
            upstream_status=response.status_code,
            retryable=False,
        )

    article_html = parse_payload.get("text")
    if not isinstance(article_html, str) or not article_html.strip():
        raise FetcherError(
            "Wikimedia API did not return parsed article HTML.",
            code="wikimedia_api_missing_content",
            status_code=502,
            upstream_status=response.status_code,
            retryable=False,
        )

    resolved_title = normalize_text(str(parse_payload.get("title") or page_title))
    final_url = _build_wikimedia_article_url(url, resolved_title)
    document = extract_document(
        article_html,
        final_url,
        settings,
        retrieval_method="wikimedia_parse_api",
    )
    document["requested_url"] = url
    document["final_url"] = final_url
    document["title"] = _normalize_display_title(parse_payload.get("displaytitle"), resolved_title)
    document["content_type"] = response.headers.get("content-type", "application/json")
    return document


async def fetch_document(url: str, settings: Settings) -> dict[str, str | int | list[str]]:
    if should_use_wikimedia_api(url, settings):
        return await fetch_wikimedia_api_document(url, settings)
    return await fetch_html(url, settings)


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
        document = await fetch_document(payload.url, settings)
        return FetchResponse.model_validate(document)
    except FetcherError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_detail()) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream returned {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {describe_exception_message(exc)}") from exc
