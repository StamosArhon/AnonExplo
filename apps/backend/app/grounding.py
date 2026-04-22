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
SOURCE_ID_PATTERN = re.compile(r"S\d+", re.IGNORECASE)
GROUPED_SOURCE_IDS_PATTERN = re.compile(
    r"\[((?:\s*S\d+\s*(?:,|;|/|\band\b)\s*)+\s*S\d+\s*)\]",
    re.IGNORECASE,
)
CITATION_SEQUENCE_PATTERN = re.compile(
    r"\[\s*S\d+\s*\](?:\s*(?:,|;|/)?\s*(?:and|or)?\s*\[\s*S\d+\s*\])+",
    re.IGNORECASE,
)
CONTEXT_PARAGRAPH_PATTERN = re.compile(r"\n\s*\n+")
DATEISH_PATTERN = re.compile(
    r"\b(?:\d{4}|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)
DIRECT_DATE_QUERY_PATTERN = re.compile(
    r"\b(?:when|date|year|month|day|time|started|start|began|begin|happened|occurred|took place|first|latest|last)\b",
    re.IGNORECASE,
)
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


def _trim_context_chunk(text: str, char_limit: int) -> str:
    if char_limit <= 0:
        return ""
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= char_limit:
        return normalized
    trimmed = normalized[:char_limit].rstrip()
    last_space = trimmed.rfind(" ")
    if last_space >= max(0, char_limit // 2):
        trimmed = trimmed[:last_space]
    return trimmed.rstrip(" ,;:")


def _chunk_context_passage(text: str, char_limit: int, overlap_chars: int) -> list[str]:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return []
    if len(normalized) <= char_limit:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + char_limit)
        if end < len(normalized):
            split_at = normalized.rfind(" ", start + max(32, char_limit // 2), end)
            if split_at > start:
                end = split_at
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap_chars)
        while start < len(normalized) and normalized[start].isspace():
            start += 1
    return chunks


def _build_context_candidates(text: str, candidate_chars: int) -> list[tuple[int, str]]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in CONTEXT_PARAGRAPH_PATTERN.split(normalized) if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    overlap_chars = max(48, candidate_chars // 5)
    candidates: list[tuple[int, str]] = []
    position = 0
    for paragraph in paragraphs:
        for chunk in _chunk_context_passage(paragraph, candidate_chars, overlap_chars):
            candidates.append((position, chunk))
            position += 1
    return candidates


def _score_context_candidate(query: str, query_terms: list[str], passage: str, position: int) -> float:
    normalized_passage = _normalize_text_for_match(passage)
    if not normalized_passage:
        return float("-inf")

    passage_terms = set(normalized_passage.split())
    matched_terms = {term for term in query_terms if term in passage_terms}
    normalized_query = _normalize_text_for_match(query)

    score = len(matched_terms) * 14.0
    if query_terms:
        score += (len(matched_terms) / len(query_terms)) * 26.0
    if normalized_query and normalized_query in normalized_passage:
        score += 34.0
    if DIRECT_DATE_QUERY_PATTERN.search(query) and DATEISH_PATTERN.search(passage):
        score += 10.0
    elif DATEISH_PATTERN.search(passage):
        score += 2.0
    score -= position * 0.35
    return score


def _select_context_excerpt(query: str, content_text: str, char_limit: int) -> str:
    normalized = content_text.replace("\r\n", "\n").strip()
    if not normalized or char_limit <= 0:
        return ""
    if len(normalized) <= char_limit:
        return normalized

    candidate_chars = min(char_limit, max(260, min(680, char_limit // 2 or char_limit)))
    query_terms = _extract_query_terms(query)
    candidates = _build_context_candidates(normalized, candidate_chars)
    if not candidates:
        return _trim_context_chunk(normalized, char_limit)

    scored_candidates = [
        (position, passage, _score_context_candidate(query, query_terms, passage, position))
        for position, passage in candidates
    ]
    scored_candidates.sort(key=lambda item: (-item[2], item[0]))

    selected: list[tuple[int, str]] = []
    selected_passages: set[str] = set()
    used_chars = 0
    joiner = "\n...\n"

    for position, passage, score in scored_candidates:
        if passage in selected_passages or (score <= 0 and selected):
            continue
        addition_cost = len(passage) + (len(joiner) if selected else 0)
        if selected and used_chars + addition_cost > char_limit:
            continue
        if not selected and len(passage) > char_limit:
            passage = _trim_context_chunk(passage, char_limit)
            addition_cost = len(passage)
        selected.append((position, passage))
        selected_passages.add(passage)
        used_chars += addition_cost
        if used_chars >= char_limit or len(selected) >= 3:
            break

    if not selected:
        return _trim_context_chunk(normalized, char_limit)

    selected.sort(key=lambda item: item[0])
    combined = joiner.join(passage for _, passage in selected)
    return _trim_context_chunk(combined, char_limit) if len(combined) > char_limit else combined


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
    query: str,
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
            source_context_limit = min(source_char_limit, remaining_chars)
            context_text = _select_context_excerpt(query, document.content_text, source_context_limit)
            context_chars_used = len(context_text)
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
        query=query,
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
            "Answer the question directly in the first sentence whenever the supplied material supports a direct answer.",
            "For yes-or-no questions, start with Yes, No, or Insufficient based only on the provided material.",
            "If the sources provide a concrete date, name, number, or event label, state it plainly before adding context.",
            "Every substantive factual claim must cite one or more supporting source IDs like [S1].",
            "Place citations at the end of the sentence they support using consecutive source IDs like [S1][S2]. Never group multiple source IDs inside one bracket, and never put citations on their own line.",
            "Do not answer from prior knowledge, training data, or unstated assumptions.",
            "If the provided material does not establish an answer, say that the sourced material is insufficient.",
            "If the sources conflict, describe the conflict and cite the competing source IDs.",
            "Keep the answer concise and specific. Do not hedge with phrases like 'the sourced material suggests' when the supplied text directly answers the question.",
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


def _normalize_citation_match(match_text: str) -> str:
    seen_ids: set[str] = set()
    ordered_ids: list[str] = []
    for source_id in SOURCE_ID_PATTERN.findall(match_text):
        normalized_id = source_id.upper()
        if normalized_id in seen_ids:
            continue
        seen_ids.add(normalized_id)
        ordered_ids.append(normalized_id)
    return "".join(f"[{source_id}]" for source_id in ordered_ids)


def normalize_grounded_answer(answer: str) -> str:
    normalized = str(answer or "").replace("\r\n", "\n").strip()
    if not normalized:
        return normalized

    normalized = GROUPED_SOURCE_IDS_PATTERN.sub(
        lambda match: _normalize_citation_match(match.group(1)),
        normalized,
    )
    normalized = CITATION_SEQUENCE_PATTERN.sub(
        lambda match: _normalize_citation_match(match.group(0)),
        normalized,
    )
    normalized = re.sub(r"([,.;:!?])\s+(\[S\d+\])", r"\1\2", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\[S\d+\])\s+([,.;:!?])", r"\1\2", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"([^\n])\n([^\n])", r"\1 \2", normalized)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
