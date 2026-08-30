import asyncio
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
    search_failures: int = 0
    context_mode: Literal["fetched_text", "fetched_plus_snippets", "search_snippets", "none"] = "none"


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
NUMBERISH_PATTERN = re.compile(r"\b\d[\d,./:-]*\b")
DIRECT_DATE_QUERY_PATTERN = re.compile(
    r"\b(?:when|date|year|month|day|time|started|start|began|begin|happened|occurred|took place|first|latest|last)\b",
    re.IGNORECASE,
)
DEFINITIONAL_QUERY_PATTERN = re.compile(
    r"^\s*(?:what|who|where)\s+(?:is|are|was|were)\b|^\s*(?:define|explain|overview|summary)\b",
    re.IGNORECASE,
)
YES_NO_QUERY_PATTERN = re.compile(
    r"^\s*(?:is|are|was|were|do|does|did|has|have|had|can|could|will|would|should)\b",
    re.IGNORECASE,
)
STATUS_QUERY_PATTERN = re.compile(
    r"\b(?:status|state|open|closed|reopen|reopened|blockade|ceasefire|resume|resumed|resuming|ongoing|current)\b",
    re.IGNORECASE,
)
LIVE_COVERAGE_HINT_PATTERN = re.compile(
    r"\b(?:live|liveblog|updates?|rolling|as it happened)\b",
    re.IGNORECASE,
)
LIVE_URL_HINT_PATTERN = re.compile(r"/(?:live|liveblog|updates?)(?:[/?#-]|$)", re.IGNORECASE)
STABLE_COVERAGE_HINT_PATTERN = re.compile(
    r"\b(?:timeline|explainer|analysis|what to know|faq|questions|guide|overview)\b",
    re.IGNORECASE,
)
DIRECT_ANSWER_HINT_PATTERN = re.compile(
    r"\b(?:timeline|date|dated|first reported|first strike|began|started|happened|occurred|phase|ceasefire|blockade|negotiations?|talks?|open|closed|resume|resumed|resuming|confirmed|denied)\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=(?:[\"'(\[]*[A-Z0-9]))")
MULTI_PART_QUERY_PATTERN = re.compile(
    r"\band\s+(?:what|who|where|when|why|how|is|are|was|were|do|does|did|has|have|had|can|could|will|would|should)\b",
    re.IGNORECASE,
)
MULTI_PART_QUERY_SPLIT_PATTERN = re.compile(
    r"(?:\s+and\s+|\s*[?!.]\s*(?:and\s+)?)"
    r"(?=(?:what|who|where|when|why|how|is|are|was|were|do|does|did|has|have|had|can|could|will|would|should)\b)",
    re.IGNORECASE,
)
TEXT_MATCH_CANONICALIZATION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bUnited States(?: of America)?\b", re.IGNORECASE), " unitedstates "),
    (re.compile(r"\bAmerican(?:s)?\b", re.IGNORECASE), " unitedstates "),
    (re.compile(r"\bUS\b"), " unitedstates "),
    (re.compile(r"\bU\.S\.A?\.?\b"), " unitedstates "),
    (re.compile(r"\bUSA\b"), " unitedstates "),
    (re.compile(r"\bIranian(?:s)?\b", re.IGNORECASE), " iran "),
    (re.compile(r"\bTehran\b", re.IGNORECASE), " iran "),
    (re.compile(r"\bIsraeli(?:s)?\b", re.IGNORECASE), " israel "),
    (re.compile(r"\bStrik(?:e|es|ing|ed)\b", re.IGNORECASE), " attack "),
    (re.compile(r"\bAttack(?:s|ed|ing)?\b", re.IGNORECASE), " attack "),
    (re.compile(r"\bNegotiat(?:e|es|ed|ing|ion|ions)\b", re.IGNORECASE), " talks "),
    (re.compile(r"\bStraits\b", re.IGNORECASE), " strait "),
    (re.compile(r"\bReopen(?:ed|ing)?\b", re.IGNORECASE), " open "),
)
COMMON_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "current",
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
    "place",
    "state",
    "status",
    "take",
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
GENERIC_STATUS_QUERY_TERMS = {
    "blockade",
    "ceasefire",
    "closed",
    "open",
    "peace",
    "phase",
    "resume",
    "resumed",
    "resuming",
    "talks",
}


def _normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, hostname, path, "", ""))


def _extract_domain(url: str) -> str:
    return urlsplit(url).hostname or "unknown"


def _canonicalize_text_for_match(text: str) -> str:
    normalized = text or ""
    for pattern, replacement in TEXT_MATCH_CANONICALIZATION_RULES:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _normalize_text_for_match(text: str) -> str:
    canonicalized = _canonicalize_text_for_match(text)
    return " ".join(QUERY_TOKEN_PATTERN.findall(canonicalized.lower()))


def _extract_query_terms(query: str) -> list[str]:
    seen_terms: set[str] = set()
    query_terms: list[str] = []
    for token in _normalize_text_for_match(query).split():
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


def _is_definitional_query(query: str) -> bool:
    return bool(DEFINITIONAL_QUERY_PATTERN.search(query or ""))


def _is_status_query(query: str) -> bool:
    normalized_query = query or ""
    return bool(YES_NO_QUERY_PATTERN.search(normalized_query) or STATUS_QUERY_PATTERN.search(normalized_query))


def _is_multi_part_query(query: str) -> bool:
    return bool(MULTI_PART_QUERY_PATTERN.search(query or ""))


def _build_search_query_variants(query: str, max_variants: int = 3) -> list[str]:
    normalized_query = " ".join((query or "").split()).strip()
    if not normalized_query or max_variants <= 1 or not _is_multi_part_query(normalized_query):
        return [normalized_query]

    clauses = [
        part.strip(" .?!")
        for part in MULTI_PART_QUERY_SPLIT_PATTERN.split(normalized_query)
        if part.strip()
    ]
    if len(clauses) <= 1:
        return [normalized_query]

    variants = [normalized_query]
    variant_keys = {normalized_query.casefold()}
    for clause in clauses:
        clause_key = clause.casefold()
        if clause_key in variant_keys:
            continue
        variants.append(clause)
        variant_keys.add(clause_key)
        if len(variants) >= max_variants:
            break
    return variants


async def _search_query_variants(
    query: str,
    search_provider: SearchProvider,
    search_limit: int,
    *,
    expansion_enabled: bool,
    max_query_variants: int,
) -> tuple[list[SearchHit], list[GroundingError]]:
    variants = (
        _build_search_query_variants(query, max_query_variants)
        if expansion_enabled
        else [query]
    )
    responses = await asyncio.gather(
        *(search_provider.search(variant, search_limit) for variant in variants),
        return_exceptions=True,
    )

    query_hits: list[SearchHit] = []
    search_errors: list[GroundingError] = []
    for variant, response in zip(variants, responses, strict=True):
        if isinstance(response, Exception):
            search_errors.append(
                GroundingError(
                    stage="search",
                    message=f"Search variant failed for '{variant}': {response}",
                    code="search_variant_failed",
                )
            )
            continue
        query_hits.extend(response)

    if not query_hits and search_errors:
        raise ProviderError(search_errors[0].message)
    return query_hits, search_errors


def _is_current_events_query(query: str) -> bool:
    normalized_query = query or ""
    return bool(
        DIRECT_DATE_QUERY_PATTERN.search(normalized_query)
        or _is_status_query(normalized_query)
        or _is_multi_part_query(normalized_query)
    )


def _is_explicit_live_query(query: str) -> bool:
    return bool(LIVE_COVERAGE_HINT_PATTERN.search(query or ""))


def _has_strong_query_coverage(query_terms: list[str], matched_terms: set[str]) -> bool:
    if not query_terms:
        return True

    required_terms = max(2, min(4, (len(query_terms) + 1) // 2))
    return len(matched_terms) >= required_terms


def _is_likely_live_candidate(candidate: GroundingSelectedSource) -> bool:
    candidate_text = " ".join(part for part in [candidate.title, candidate.url] if part)
    return bool(
        LIVE_COVERAGE_HINT_PATTERN.search(candidate_text)
        or LIVE_URL_HINT_PATTERN.search(candidate.url)
    )


def _extract_core_query_terms(query: str, query_terms: list[str]) -> set[str]:
    if not (_is_status_query(query) or _is_multi_part_query(query)):
        return set(query_terms)
    return {term for term in query_terms if term not in GENERIC_STATUS_QUERY_TERMS}


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
    raw_candidate_text = " ".join(part for part in [candidate.title, candidate.snippet] if part).strip()
    normalized_query = _normalize_text_for_match(query)
    definitional_query = _is_definitional_query(query)
    status_query = _is_status_query(query)
    direct_date_query = bool(DIRECT_DATE_QUERY_PATTERN.search(query))
    current_events_query = _is_current_events_query(query)
    explicit_live_query = _is_explicit_live_query(query)
    likely_live_candidate = _is_likely_live_candidate(candidate)
    stable_candidate = bool(STABLE_COVERAGE_HINT_PATTERN.search(raw_candidate_text))

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

    if direct_date_query:
        if DATEISH_PATTERN.search(raw_candidate_text):
            score += 16.0
        if NUMBERISH_PATTERN.search(raw_candidate_text):
            score += 6.0
        if DIRECT_ANSWER_HINT_PATTERN.search(raw_candidate_text):
            score += 8.0
        if likely_live_candidate and not DATEISH_PATTERN.search(raw_candidate_text):
            score -= 10.0
    elif status_query:
        if DIRECT_ANSWER_HINT_PATTERN.search(raw_candidate_text):
            score += 8.0
        if likely_live_candidate:
            score -= 4.0
    elif definitional_query and DIRECT_ANSWER_HINT_PATTERN.search(raw_candidate_text):
        score += 6.0

    if current_events_query and not explicit_live_query:
        if stable_candidate:
            score += 6.0
        if likely_live_candidate:
            score -= 8.0

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
        if definitional_query:
            score += preferred_domain_boost
        else:
            score += min(preferred_domain_boost, 4.0)

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
    candidates_by_domain: dict[str, list[tuple[GroundingSelectedSource, float]]] = {}
    domain_order: list[str] = []
    for candidate, score in scored_candidates:
        if candidate.domain not in candidates_by_domain:
            candidates_by_domain[candidate.domain] = []
            domain_order.append(candidate.domain)
        candidates_by_domain[candidate.domain].append((candidate, score))

    primary_pass: list[GroundingSelectedSource] = []
    fallback_pass: list[GroundingSelectedSource] = []
    prefer_non_live = _is_current_events_query(query) and not _is_explicit_live_query(query) and not _is_definitional_query(query)

    for domain in domain_order:
        domain_candidates = candidates_by_domain[domain]
        primary_candidate, primary_score = domain_candidates[0]
        promoted_index: int | None = None

        if prefer_non_live and _is_likely_live_candidate(primary_candidate):
            for index, (candidate, score) in enumerate(domain_candidates[1:], start=1):
                if _is_likely_live_candidate(candidate):
                    continue
                if primary_score - score <= 10.0:
                    primary_candidate = candidate
                    promoted_index = index
                    break

        primary_pass.append(primary_candidate)

        for index, (candidate, _) in enumerate(domain_candidates):
            if candidate.source_id == primary_candidate.source_id:
                continue
            if promoted_index is not None and index == 0:
                fallback_pass.append(candidate)
                continue
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


def _split_context_sentences(text: str) -> list[str]:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return []

    sentences = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(normalized) if part.strip()]
    return sentences or [normalized]


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
        sentences = _split_context_sentences(paragraph)
        if len(sentences) <= 1:
            for chunk in _chunk_context_passage(paragraph, candidate_chars, overlap_chars):
                candidates.append((position, chunk))
                position += 1
            continue

        for start_index in range(len(sentences)):
            single_sentence = _trim_context_chunk(sentences[start_index], candidate_chars)
            if single_sentence:
                candidates.append((position + start_index, single_sentence))

            for end_index in range(start_index + 1, min(len(sentences), start_index + 3)):
                candidate_text = " ".join(sentences[start_index : end_index + 1]).strip()
                if len(candidate_text) > candidate_chars and end_index > start_index + 1:
                    break
                trimmed_candidate = _trim_context_chunk(candidate_text, candidate_chars)
                if trimmed_candidate:
                    candidates.append((position + start_index, trimmed_candidate))
        position += len(sentences)
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
        if len(matched_terms) >= max(2, len(query_terms) // 2):
            score += 10.0
    if normalized_query and normalized_query in normalized_passage:
        score += 34.0
    if DIRECT_DATE_QUERY_PATTERN.search(query) and DATEISH_PATTERN.search(passage):
        score += 10.0
    elif _is_status_query(query) and DIRECT_ANSWER_HINT_PATTERN.search(passage):
        score += 8.0
    elif DATEISH_PATTERN.search(passage):
        score += 2.0
    score -= min(position * 0.18, 10.0)
    return score


def _source_matches_query_strongly(query: str, source: GroundingSelectedSource) -> bool:
    query_terms = _extract_query_terms(query)
    if not query_terms:
        return False

    source_text = " ".join(part for part in [source.title, source.snippet, source.url] if part)
    source_terms = set(_normalize_text_for_match(source_text).split())
    matched_terms = {term for term in query_terms if term in source_terms}
    coverage_ratio = len(matched_terms) / len(query_terms)
    has_direct_signal = bool(DIRECT_ANSWER_HINT_PATTERN.search(source_text))
    core_query_terms = _extract_core_query_terms(query, query_terms)
    matched_core_terms = {term for term in core_query_terms if term in source_terms}

    if _is_status_query(query) or _is_multi_part_query(query):
        if not matched_core_terms:
            return False
        return (
            coverage_ratio >= 0.4
            or (_has_strong_query_coverage(query_terms, matched_terms) and has_direct_signal)
            or len(matched_core_terms) >= 2
        )

    return has_direct_signal or coverage_ratio >= 0.5 or _has_strong_query_coverage(query_terms, matched_terms)


def _filter_snippet_sources_for_query(
    query: str,
    sources: list[GroundingSelectedSource],
    *,
    max_sources: int,
) -> list[GroundingSelectedSource]:
    snippet_sources = [source for source in sources if source.snippet.strip()]
    ranked_sources = _rank_sources(
        query,
        snippet_sources,
        preferred_domains=[],
        preferred_domain_boost=0.0,
    )
    strong_sources = [source for source in ranked_sources if _source_matches_query_strongly(query, source)]
    if strong_sources:
        return strong_sources[:max_sources]
    return ranked_sources[:max_sources]


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

    if not scored_candidates:
        return _trim_context_chunk(normalized, char_limit)

    best_position, best_passage, best_score = scored_candidates[0]
    if best_score <= 0:
        return _trim_context_chunk(normalized, char_limit)

    best_passage_terms = set(_normalize_text_for_match(best_passage).split())
    best_matched_terms = {term for term in query_terms if term in best_passage_terms}

    if (
        DIRECT_DATE_QUERY_PATTERN.search(query)
        and DATEISH_PATTERN.search(best_passage)
        and _has_strong_query_coverage(query_terms, best_matched_terms)
        and not _is_multi_part_query(query)
    ):
        return _trim_context_chunk(best_passage, char_limit)
    if (
        _is_status_query(query)
        and DIRECT_ANSWER_HINT_PATTERN.search(best_passage)
        and _has_strong_query_coverage(query_terms, best_matched_terms)
        and not _is_multi_part_query(query)
    ):
        return _trim_context_chunk(best_passage, char_limit)

    selected: list[tuple[int, str]] = [(best_position, best_passage)]
    selected_passages: set[str] = {best_passage}
    used_chars = len(best_passage)
    covered_terms = set(best_matched_terms)
    joiner = "\n...\n"

    for position, passage, score in scored_candidates[1:]:
        if passage in selected_passages or score <= 0:
            continue

        passage_terms = {term for term in query_terms if term in _normalize_text_for_match(passage).split()}
        if covered_terms and not (passage_terms - covered_terms):
            continue

        addition_cost = len(passage) + len(joiner)
        if used_chars + addition_cost > char_limit:
            continue

        selected.append((position, passage))
        selected_passages.add(passage)
        used_chars += addition_cost
        covered_terms.update(passage_terms)
        if len(selected) >= 2 or (query_terms and len(covered_terms) == len(query_terms)):
            break

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
    snippet_label: str = "Search snippet:",
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
                    snippet_label,
                    snippet_text,
                ]
            )
        )

    return "\n\n---\n\n".join(context_parts), used_context_chars


def _compose_failed_source_snippet_context(
    query: str,
    fetch_results: list[tuple[GroundingSelectedSource, FetchDocument | None, GroundingError | None]],
    total_context_chars: int,
) -> tuple[str, int]:
    failed_sources_with_snippets = [
        source
        for source, document, _ in fetch_results
        if document is None and source.snippet.strip()
    ]
    return _compose_snippet_context(
        selected_sources=_filter_snippet_sources_for_query(
            query,
            failed_sources_with_snippets,
            max_sources=2,
        ),
        total_context_chars=min(total_context_chars, 640),
        snippet_label="Search snippet fallback:",
    )


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
    query_expansion_enabled: bool = True,
    max_query_variants: int = 3,
) -> tuple[GroundingBundle, str]:
    query_hits, search_errors = await _search_query_variants(
        query,
        search_provider,
        search_limit,
        expansion_enabled=query_expansion_enabled,
        max_query_variants=max_query_variants,
    )
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
    fetched_sources, fetch_errors, grounding_context, used_context_chars = _compose_context(
        query=query,
        selected_sources=selected_sources,
        fetch_results=fetch_results,
        source_char_limit=source_char_limit,
        total_context_chars=total_context_chars,
        preview_chars=preview_chars,
    )
    context_mode: Literal["fetched_text", "fetched_plus_snippets", "search_snippets", "none"] = "none"
    if grounding_context.strip():
        context_mode = "fetched_text"
        remaining_chars = max(0, total_context_chars - used_context_chars)
        if remaining_chars > 0:
            snippet_context, snippet_chars_used = _compose_failed_source_snippet_context(
                query=query,
                fetch_results=fetch_results,
                total_context_chars=remaining_chars,
            )
            if snippet_context.strip():
                grounding_context = "\n\n---\n\n".join([grounding_context, snippet_context])
                used_context_chars += snippet_chars_used
                context_mode = "fetched_plus_snippets"
    else:
        grounding_context, used_context_chars = _compose_snippet_context(
            selected_sources=_filter_snippet_sources_for_query(
                query,
                selected_sources,
                max_sources=max(1, min(len(selected_sources), 3)),
            ),
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
            failed_sources=len(fetch_errors),
            search_failures=len(search_errors),
            grounding_characters=used_context_chars,
            context_mode=context_mode,
        ),
        search_results=search_results,
        selected_sources=selected_sources,
        fetched_sources=fetched_sources,
        errors=[*search_errors, *fetch_errors],
    )
    return bundle, grounding_context


def build_grounded_model_request(
    query: str,
    grounding_context: str,
    temperature: float,
    context_mode: Literal["fetched_text", "fetched_plus_snippets", "search_snippets", "none"] = "fetched_text",
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
    elif context_mode == "fetched_plus_snippets":
        context_heading = "Grounded sources and snippet fallbacks:"
        context_guidance = (
            "Answer the user's question using the grounded source text below. "
            "Prefer fetched article text when it directly answers the question, and use labeled search-snippet fallbacks only when fetches were unavailable for some selected sources."
        )
    prompt = "\n\n".join(
        [
            context_guidance,
            "Answer the question directly in the first sentence whenever the supplied material supports a direct answer.",
            "For yes-or-no questions, start with Yes, No, or Insufficient based only on the provided material.",
            "If the sources provide a concrete date, name, number, or event label, state it plainly before adding context.",
            "Use the smallest sufficient set of sources. If one source directly answers the question, lead with that answer and use other sources only to confirm it or to describe a conflict.",
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
    elif context_mode == "fetched_plus_snippets":
        system_prompt = "\n\n".join(
            [
                system_prompt,
                "Some sources were fetched as article text, while other selected sources are available only as labeled search-result snippets. "
                "Prefer fetched article text when possible, and treat snippet-backed details as lower-confidence summaries rather than full article extracts.",
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
