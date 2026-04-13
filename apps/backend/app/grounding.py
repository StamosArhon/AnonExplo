import asyncio
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel

from app.providers import FetchDocument, FetcherClient, GroundedModelRequest, ProviderError, SearchHit, SearchProvider


class GroundingSearchResult(BaseModel):
    rank: int
    title: str
    url: str
    normalized_url: str
    domain: str
    snippet: str = ""
    engine: str | None = None
    status: Literal["selected", "duplicate", "unselected"] = "unselected"
    source_id: str | None = None
    duplicate_of: str | None = None


class GroundingSelectedSource(BaseModel):
    source_id: str
    search_rank: int
    title: str
    url: str
    normalized_url: str
    domain: str
    snippet: str = ""
    engine: str | None = None


class GroundingFetchedSource(BaseModel):
    source_id: str
    search_rank: int
    title: str
    url: str
    normalized_url: str
    domain: str
    final_url: str
    document_title: str | None = None
    excerpt: str = ""
    context_text: str = ""
    context_chars_used: int = 0
    content_char_count: int = 0
    word_count: int = 0
    content_type: str | None = None
    engine: str | None = None


class GroundingError(BaseModel):
    stage: Literal["search", "fetch", "grounding", "model"]
    message: str
    source_id: str | None = None
    url: str | None = None


class GroundingSummary(BaseModel):
    search_results: int
    unique_search_results: int
    selected_sources: int
    fetched_sources: int
    failed_sources: int
    grounding_characters: int


class GroundingBundle(BaseModel):
    query: str
    summary: GroundingSummary
    search_results: list[GroundingSearchResult]
    selected_sources: list[GroundingSelectedSource]
    fetched_sources: list[GroundingFetchedSource]
    errors: list[GroundingError]


def _normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, hostname, path, "", ""))


def _extract_domain(url: str) -> str:
    return urlsplit(url).hostname or "unknown"


def _build_search_results(query_hits: list[SearchHit]) -> tuple[list[GroundingSearchResult], list[GroundingSelectedSource]]:
    search_results: list[GroundingSearchResult] = []
    source_candidates: list[GroundingSelectedSource] = []
    seen_urls: dict[str, str] = {}

    for rank, hit in enumerate(query_hits, start=1):
        normalized_url = _normalize_url(hit.url)
        domain = _extract_domain(hit.url)

        if normalized_url in seen_urls:
            existing_source_id = seen_urls[normalized_url]
            search_results.append(
                GroundingSearchResult(
                    rank=rank,
                    title=hit.title,
                    url=hit.url,
                    normalized_url=normalized_url,
                    domain=domain,
                    snippet=hit.snippet,
                    engine=hit.engine,
                    status="duplicate",
                    source_id=existing_source_id,
                    duplicate_of=existing_source_id,
                )
            )
            continue

        source_id = f"S{len(source_candidates) + 1}"
        selected_source = GroundingSelectedSource(
            source_id=source_id,
            search_rank=rank,
            title=hit.title,
            url=hit.url,
            normalized_url=normalized_url,
            domain=domain,
            snippet=hit.snippet,
            engine=hit.engine,
        )
        source_candidates.append(selected_source)
        seen_urls[normalized_url] = source_id
        search_results.append(
            GroundingSearchResult(
                rank=rank,
                title=hit.title,
                url=hit.url,
                normalized_url=normalized_url,
                domain=domain,
                snippet=hit.snippet,
                engine=hit.engine,
                source_id=source_id,
            )
        )

    return search_results, source_candidates


def _pick_sources(
    search_results: list[GroundingSearchResult],
    source_candidates: list[GroundingSelectedSource],
    fetch_limit: int,
) -> tuple[list[GroundingSearchResult], list[GroundingSelectedSource]]:
    selected_sources: list[GroundingSelectedSource] = []
    remaining_candidates: list[GroundingSelectedSource] = []
    seen_domains: set[str] = set()

    for candidate in source_candidates:
        if len(selected_sources) >= fetch_limit:
            remaining_candidates.append(candidate)
            continue

        if candidate.domain not in seen_domains:
            selected_sources.append(candidate)
            seen_domains.add(candidate.domain)
        else:
            remaining_candidates.append(candidate)

    for candidate in remaining_candidates:
        if len(selected_sources) >= fetch_limit:
            break
        selected_sources.append(candidate)

    selected_ids = {source.source_id for source in selected_sources}
    updated_results = [
        result.model_copy(update={"status": "selected"})
        if result.source_id in selected_ids and result.status != "duplicate"
        else result
        for result in search_results
    ]
    return updated_results, selected_sources


async def _fetch_source(source: GroundingSelectedSource, fetcher_client: FetcherClient) -> tuple[GroundingSelectedSource, FetchDocument | None, GroundingError | None]:
    try:
        document = await fetcher_client.fetch(source.url)
        if isinstance(document, dict):
            document = FetchDocument.model_validate(document)
    except ProviderError as exc:
        return source, None, GroundingError(
            stage="fetch",
            message=str(exc),
            source_id=source.source_id,
            url=source.url,
        )
    return source, document, None


def _compose_context(
    selected_sources: list[GroundingSelectedSource],
    fetch_results: list[tuple[GroundingSelectedSource, FetchDocument | None, GroundingError | None]],
    source_char_limit: int,
    total_context_chars: int,
    preview_chars: int,
) -> tuple[list[GroundingFetchedSource], list[GroundingError], str, int]:
    fetched_sources: list[GroundingFetchedSource] = []
    errors = [error for _, _, error in fetch_results if error is not None]
    context_parts: list[str] = []
    used_context_chars = 0

    for source, document, _ in fetch_results:
        if document is None:
            continue

        if used_context_chars >= total_context_chars:
            context_text = ""
            context_chars_used = 0
        else:
            remaining_chars = total_context_chars - used_context_chars
            context_chars_used = min(len(document.content_text), source_char_limit, remaining_chars)
            context_text = document.content_text[:context_chars_used]
            used_context_chars += context_chars_used

        fetched_sources.append(
            GroundingFetchedSource(
                source_id=source.source_id,
                search_rank=source.search_rank,
                title=source.title,
                url=source.url,
                normalized_url=source.normalized_url,
                domain=source.domain,
                final_url=document.final_url,
                document_title=document.title or None,
                excerpt=document.excerpt[:preview_chars],
                context_text=context_text,
                context_chars_used=context_chars_used,
                content_char_count=document.content_char_count,
                word_count=document.word_count,
                content_type=document.content_type,
                engine=source.engine,
            )
        )

        if context_chars_used > 0:
            context_parts.append(
                "\n".join(
                    [
                        f"[{source.source_id}] {document.title or source.title}",
                        f"URL: {document.final_url}",
                        "Source text:",
                        context_text,
                    ]
                )
            )

    return fetched_sources, errors, "\n\n---\n\n".join(context_parts), used_context_chars


async def build_grounding_bundle(
    *,
    query: str,
    search_provider: SearchProvider,
    fetcher_client: FetcherClient,
    search_limit: int,
    fetch_limit: int,
    source_char_limit: int,
    total_context_chars: int,
    preview_chars: int,
) -> tuple[GroundingBundle, str]:
    query_hits = await search_provider.search(query, search_limit)
    search_results, source_candidates = _build_search_results(query_hits)
    search_results, selected_sources = _pick_sources(search_results, source_candidates, fetch_limit)

    fetch_results = await asyncio.gather(*[_fetch_source(source, fetcher_client) for source in selected_sources])
    fetched_sources, errors, grounding_context, used_context_chars = _compose_context(
        selected_sources=selected_sources,
        fetch_results=fetch_results,
        source_char_limit=source_char_limit,
        total_context_chars=total_context_chars,
        preview_chars=preview_chars,
    )
    bundle = GroundingBundle(
        query=query,
        summary=GroundingSummary(
            search_results=len(search_results),
            unique_search_results=len(source_candidates),
            selected_sources=len(selected_sources),
            fetched_sources=len(fetched_sources),
            failed_sources=len(errors),
            grounding_characters=used_context_chars,
        ),
        search_results=search_results,
        selected_sources=selected_sources,
        fetched_sources=fetched_sources,
        errors=errors,
    )
    return bundle, grounding_context


def build_grounded_model_request(
    query: str,
    grounding_context: str,
    temperature: float,
    additional_system_prompt: str | None = None,
) -> GroundedModelRequest:
    prompt = "\n\n".join(
        [
            "Answer the user's question using only the grounded source text below.",
            "Cite supporting sources inline using source IDs like [S1].",
            "If the sources are missing needed facts, say so plainly instead of guessing.",
            f"Question: {query}",
            "Grounded sources:",
            grounding_context,
        ]
    )
    system_prompt = (
        "You are a privacy-first local assistant. Use the supplied grounded sources, be explicit about uncertainty, "
        "and do not invent facts that are not supported by the provided source text."
    )
    if isinstance(additional_system_prompt, str) and additional_system_prompt.strip():
        system_prompt = "\n\n".join(
            [
                system_prompt,
                "Additional user instructions:",
                additional_system_prompt.strip(),
            ]
        )
    return GroundedModelRequest(prompt=prompt, system_prompt=system_prompt, temperature=temperature)
