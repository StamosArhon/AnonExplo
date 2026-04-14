import re
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field

from app.providers import (
    FetchDocument,
    FetcherClient,
    FetcherRequestError,
    GroundedModelRequest,
    ProviderError,
    SearchHit,
    SearchProvider,
)


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
    retrieval_method: str = "direct_html"
    content_quality: str = "usable"
    warnings: list[str] = Field(default_factory=list)
    engine: str | None = None


class GroundingError(BaseModel):
    stage: Literal["search", "fetch", "grounding", "model"]
    message: str
    code: str | None = None
    upstream_status: int | None = None
    retryable: bool | None = None
    source_id: str | None = None
    url: str | None = None


class GroundingSummary(BaseModel):
    search_results: int
    unique_search_results: int
    selected_sources: int
    fetched_sources: int
    failed_sources: int
    grounding_characters: int
    context_mode: Literal["fetched_text", "search_snippets", "none"] = "none"


class GroundingBundle(BaseModel):
    query: str
    summary: GroundingSummary
    search_results: list[GroundingSearchResult]
    selected_sources: list[GroundingSelectedSource]
    fetched_sources: list[GroundingFetchedSource]
    errors: list[GroundingError]


QUERY_TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
COMMON_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "took",
    "tookplace",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def _normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, hostname, path, "", ""))


def _extract_domain(url: str) -> str:
    return urlsplit(url).hostname or "unknown"


def _normalize_text_for_match(text: str) -> str:
    return " ".join(QUERY_TOKEN_PATTERN.findall(text.lower()))


def _extract_query_terms(query: str) -> list[str]:
    seen_terms: set[str] = set()
    query_terms: list[str] = []
    for token in QUERY_TOKEN_PATTERN.findall(query.lower()):
        if token in COMMON_QUERY_STOPWORDS:
            continue
        if token not in seen_terms:
            query_terms.append(token)
            seen_terms.add(token)
    return query_terms


def _parse_preferred_domains(preferred_domains: str) -> list[str]:
    domains: list[str] = []
    seen_domains: set[str] = set()
    for item in preferred_domains.split(","):
        normalized = item.strip().lower()
        if not normalized or normalized in seen_domains:
            continue
        domains.append(normalized)
        seen_domains.add(normalized)
    return domains


def _domain_matches_preference(domain: str, preferred_domains: list[str]) -> bool:
    normalized_domain = domain.strip().lower()
    if not normalized_domain:
        return False
    return any(
        normalized_domain == preferred_domain or normalized_domain.endswith(f".{preferred_domain}")
        for preferred_domain in preferred_domains
    )


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


def _score_source(
    query: str,
    query_terms: list[str],
    candidate: GroundingSelectedSource,
    preferred_domains: list[str],
    preferred_domain_boost: float,
) -> float:
    title_match_text = _normalize_text_for_match(candidate.title)
    snippet_match_text = _normalize_text_for_match(candidate.snippet)
    combined_match_text = " ".join(
        part for part in [title_match_text, snippet_match_text, _normalize_text_for_match(candidate.url)] if part
    )
    normalized_query = _normalize_text_for_match(query)

    title_terms = set(title_match_text.split())
    snippet_terms = set(snippet_match_text.split())
    combined_terms = set(combined_match_text.split())

    title_matches = sum(1 for term in query_terms if term in title_terms)
    snippet_matches = sum(1 for term in query_terms if term in snippet_terms)
    combined_matches = {term for term in query_terms if term in combined_terms}

    score = max(0.0, 100.0 - (candidate.search_rank * 4.0))
    score += title_matches * 12.0
    score += snippet_matches * 5.0
    score += len(combined_matches) * 3.0

    if normalized_query:
        if normalized_query in title_match_text:
            score += 28.0
        elif normalized_query in combined_match_text:
            score += 18.0

    if query_terms:
        coverage_ratio = len(combined_matches) / len(query_terms)
        score += coverage_ratio * 24.0
        if title_matches == len(query_terms):
            score += 12.0
        elif title_matches >= max(2, len(query_terms) // 2):
            score += 6.0

    if candidate.title.strip():
        score += 2.0
    if candidate.snippet.strip():
        score += 2.0

    if (
        preferred_domain_boost > 0
        and preferred_domains
        and _domain_matches_preference(candidate.domain, preferred_domains)
        and (combined_matches or (normalized_query and normalized_query in combined_match_text))
    ):
        score += preferred_domain_boost

    return score


def _rank_sources(
    query: str,
    source_candidates: list[GroundingSelectedSource],
    preferred_domains: list[str],
    preferred_domain_boost: float,
) -> list[GroundingSelectedSource]:
    query_terms = _extract_query_terms(query)
    scored_candidates = [
        (
            candidate,
            _score_source(
                query,
                query_terms,
                candidate,
                preferred_domains,
                preferred_domain_boost,
            ),
        )
        for candidate in source_candidates
    ]
    scored_candidates.sort(key=lambda item: (-item[1], item[0].search_rank, item[0].domain, item[0].normalized_url))

    ranked_candidates = [candidate for candidate, _ in scored_candidates]
    primary_pass: list[GroundingSelectedSource] = []
    fallback_pass: list[GroundingSelectedSource] = []
    seen_domains: set[str] = set()

    for candidate in ranked_candidates:
        if candidate.domain not in seen_domains:
            primary_pass.append(candidate)
            seen_domains.add(candidate.domain)
        else:
            fallback_pass.append(candidate)

    return primary_pass + fallback_pass


async def _fetch_selected_sources(
    ranked_candidates: list[GroundingSelectedSource],
    fetch_limit: int,
    fetcher_client: FetcherClient,
) -> tuple[list[GroundingSelectedSource], list[tuple[GroundingSelectedSource, FetchDocument | None, GroundingError | None]]]:
    attempted_sources: list[GroundingSelectedSource] = []
    fetch_results: list[tuple[GroundingSelectedSource, FetchDocument | None, GroundingError | None]] = []
    successful_fetches = 0
    blocked_domains: set[str] = set()

    for candidate in ranked_candidates:
        if successful_fetches >= fetch_limit:
            break
        if candidate.domain in blocked_domains:
            continue

        attempted_sources.append(candidate)
        fetch_result = await _fetch_source(candidate, fetcher_client)
        fetch_results.append(fetch_result)
        _, document, error = fetch_result
        if document is not None:
            successful_fetches += 1
            continue

        if error and error.code in {"blocked_by_remote_policy", "upstream_forbidden", "upstream_rate_limited"}:
            blocked_domains.add(candidate.domain)

    return attempted_sources, fetch_results


def _mark_selected_results(
    search_results: list[GroundingSearchResult],
    selected_sources: list[GroundingSelectedSource],
) -> list[GroundingSearchResult]:
    selected_ids = {source.source_id for source in selected_sources}
    return [
        result.model_copy(update={"status": "selected"})
        if result.source_id in selected_ids and result.status != "duplicate"
        else result
        for result in search_results
    ]


async def _fetch_source(source: GroundingSelectedSource, fetcher_client: FetcherClient) -> tuple[GroundingSelectedSource, FetchDocument | None, GroundingError | None]:
    try:
        document = await fetcher_client.fetch(source.url)
        if isinstance(document, dict):
            document = FetchDocument.model_validate(document)
        if document.content_quality == "thin":
            warning_message = " ".join(document.warnings).strip()
            message = (
                f"Fetch returned only thin page content via {document.retrieval_method} "
                f"({document.content_char_count} chars, {document.word_count} words)."
            )
            if warning_message:
                message = f"{message} {warning_message}"
            return source, None, GroundingError(
                stage="fetch",
                message=message,
                code="content_too_thin",
                retryable=False,
                source_id=source.source_id,
                url=source.url,
            )
    except FetcherRequestError as exc:
        return source, None, GroundingError(
            stage="fetch",
            message=str(exc),
            code=exc.code,
            upstream_status=exc.upstream_status,
            retryable=exc.retryable,
            source_id=source.source_id,
            url=source.url,
        )
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
                retrieval_method=document.retrieval_method,
                content_quality=document.content_quality,
                warnings=document.warnings,
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


def _compose_snippet_context(
    selected_sources: list[GroundingSelectedSource],
    total_context_chars: int,
) -> tuple[str, int]:
    context_parts: list[str] = []
    used_context_chars = 0

    for source in selected_sources:
        snippet = source.snippet.strip()
        if not snippet or used_context_chars >= total_context_chars:
            continue

        remaining_chars = total_context_chars - used_context_chars
        snippet_text = snippet[:remaining_chars]
        used_context_chars += len(snippet_text)
        context_parts.append(
            "\n".join(
                [
                    f"[{source.source_id}] {source.title}",
                    f"URL: {source.url}",
                    "Search snippet:",
                    snippet_text,
                ]
            )
        )

    return "\n\n---\n\n".join(context_parts), used_context_chars


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
    preferred_domains: str = "",
    preferred_domain_boost: float = 0.0,
) -> tuple[GroundingBundle, str]:
    query_hits = await search_provider.search(query, search_limit)
    search_results, source_candidates = _build_search_results(query_hits)
    ranked_candidates = _rank_sources(
        query,
        source_candidates,
        _parse_preferred_domains(preferred_domains),
        preferred_domain_boost,
    )
    selected_sources, fetch_results = await _fetch_selected_sources(
        ranked_candidates=ranked_candidates,
        fetch_limit=fetch_limit,
        fetcher_client=fetcher_client,
    )
    search_results = _mark_selected_results(search_results, selected_sources)
    fetched_sources, errors, grounding_context, used_context_chars = _compose_context(
        selected_sources=selected_sources,
        fetch_results=fetch_results,
        source_char_limit=source_char_limit,
        total_context_chars=total_context_chars,
        preview_chars=preview_chars,
    )
    context_mode: Literal["fetched_text", "search_snippets", "none"] = "none"
    if grounding_context.strip():
        context_mode = "fetched_text"
    else:
        grounding_context, used_context_chars = _compose_snippet_context(
            selected_sources=selected_sources,
            total_context_chars=total_context_chars,
        )
        if grounding_context.strip():
            context_mode = "search_snippets"

    bundle = GroundingBundle(
        query=query,
        summary=GroundingSummary(
            search_results=len(search_results),
            unique_search_results=len(source_candidates),
            selected_sources=len(selected_sources),
            fetched_sources=len(fetched_sources),
            failed_sources=len(errors),
            grounding_characters=used_context_chars,
            context_mode=context_mode,
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
    context_mode: Literal["fetched_text", "search_snippets", "none"] = "fetched_text",
    additional_system_prompt: str | None = None,
) -> GroundedModelRequest:
    context_heading = "Grounded sources:"
    context_guidance = "Answer the user's question using only the grounded source text below."
    if context_mode == "search_snippets":
        context_heading = "Search result snippets:"
        context_guidance = (
            "Answer the user's question using only the supporting search-result snippets below. "
            "Treat them as lower-confidence summaries because article fetches were unavailable."
        )
    prompt = "\n\n".join(
        [
            context_guidance,
            "Every substantive factual claim must cite one or more supporting source IDs like [S1].",
            "Do not answer from prior knowledge, training data, or unstated assumptions.",
            "If the provided material does not establish an answer, say that the sourced material is insufficient.",
            "If the sources conflict, describe the conflict and cite the competing source IDs.",
            f"Question: {query}",
            context_heading,
            grounding_context,
        ]
    )
    system_prompt = (
        "You are a privacy-first local assistant. Use only the supplied grounded sources, be explicit about "
        "uncertainty, and do not invent facts that are not supported by the provided source text. Do not mention "
        "your training data, knowledge cutoff, or prior knowledge; evaluate only the grounded sources in this request."
    )
    if context_mode == "search_snippets":
        system_prompt = "\n\n".join(
            [
                system_prompt,
                "The current request is using search-result snippets because article fetches were unavailable. "
                "Do not overclaim details that the snippets do not explicitly state.",
            ]
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
