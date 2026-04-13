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
    pass


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
    fetch_user_agent: str = Field(
        default="AnonExploFetcher/0.1",
        validation_alias="FETCH_USER_AGENT",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


class FetchRequest(BaseModel):
    url: str = Field(min_length=1)


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


def extract_document(html: str, source_url: str, max_chars: int) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "nav", "form"]):
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

    content_text = "\n\n".join(text_blocks)[:max_chars]
    content_char_count = len(content_text)
    word_count = len([word for word in content_text.split(" ") if word])
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
    }


async def fetch_html(url: str, settings: Settings) -> dict[str, str]:
    headers = {
        "User-Agent": settings.fetch_user_agent,
        "Accept": "text/html,application/xhtml+xml",
    }
    timeout = httpx.Timeout(settings.fetch_request_timeout_seconds)

    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise FetcherError("Only HTML pages are supported by the fetch pipeline.")

            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > settings.fetch_max_response_bytes:
                    raise FetcherError("Fetched page exceeded the configured size limit.")

    html = chunks.decode("utf-8", errors="replace")
    document = extract_document(html, url, settings.fetch_max_text_chars)
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
) -> dict[str, str]:
    try:
        validate_requested_url(payload.url)
        return await fetch_html(payload.url, settings)
    except FetcherError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream returned {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {exc}") from exc
