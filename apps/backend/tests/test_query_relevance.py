import unittest
import unicodedata
from unittest.mock import AsyncMock, patch

import httpx

from app.grounding import (
    _build_search_query_variants, _extract_query_terms, _normalize_text_for_match,
    _select_context_excerpt, build_grounded_model_request, build_grounding_bundle,
    _build_search_results, _rank_sources,
)
from app.providers import FetchDocument, FetcherRequestError, SearchHit, SearxngSearchProvider
from app.query_text import infer_greek_language, question_clauses, is_greek_current_query


class QueryTextTests(unittest.TestCase):
    def test_greek_matching_keeps_letters_and_folds_accents_sigma(self):
        self.assertEqual(_normalize_text_for_match("ΚΟΣΜΟΣ κόσμος κοσμοσ"), "κοσμοσ κοσμοσ κοσμοσ")
        self.assertEqual(_extract_query_terms("Πού είναι το Εθνικό Αρχαιολογικό Μουσείο;"),
                         ["εθνικο", "αρχαιολογικο", "μουσειο"])
        self.assertEqual(_extract_query_terms(unicodedata.normalize("NFD", "Μουσείο")), ["μουσειο"])

    def test_language_detection_handles_mixed_technical_names(self):
        self.assertEqual(infer_greek_language("Τι είναι Docker Compose;"), "el")
        self.assertEqual(infer_greek_language("Εθνικό Αρχαιολογικό Μουσείο"), "el")
        self.assertEqual(infer_greek_language("What does the symbol α mean?"), "")
        self.assertEqual(infer_greek_language("Docker Compose networking"), "")

    def test_greek_recency_not_place_name_or_bare_latest_version(self):
        self.assertTrue(is_greek_current_query("Ποιες είναι οι σημερινές εξελίξεις;"))
        self.assertTrue(is_greek_current_query("Τι συμβαίνει ΤΩΡΑ;"))
        self.assertFalse(is_greek_current_query("Νέα Φιλαδέλφεια μουσείο"))
        self.assertFalse(is_greek_current_query("Τι είναι το λογισμικό ανοικτού κώδικα;"))

    def test_greek_and_english_punctuation_split(self):
        for query in ("What is Python? When was Docker created?",
                      "Τι είναι η Python; Πότε δημιουργήθηκε το Docker;",
                      "Τι είναι η Python και πότε δημιουργήθηκε το Docker;"):
            variants = _build_search_query_variants(query)
            self.assertEqual(len(variants), 3)
            self.assertEqual(variants[0], query)
            self.assertIn("Python", variants[1])
            self.assertIn("Docker", variants[2])

    def test_no_split_for_conjunctions_operators_quotes_or_orphaned_pronouns(self):
        for query in ("Python and Docker", "ιστορία και πολιτισμός",
                      '"what is Python and when was Docker created"',
                      "site:python.org what is Python and when was Docker created?",
                      "What is Python and when was it created?",
                      "Τι είναι η Python και πότε δημιουργήθηκε αυτή;"):
            self.assertEqual(_build_search_query_variants(query), [query])

    def test_variant_budget_and_deduplication(self):
        query = "What is Python? What is Docker? What is Linux?"
        self.assertEqual(len(_build_search_query_variants(query, 2)), 2)
        self.assertEqual(_build_search_query_variants(query, 1), [query])
        self.assertEqual(question_clauses("What is Python? What is Python?"), ["What is Python"])

    def test_greek_relevant_excerpt_beats_long_irrelevant_intro(self):
        text = ("Generic introduction without relevant information. " * 80
                + "\n\nΤο Εθνικό Αρχαιολογικό Μουσείο βρίσκεται στην Αθήνα.")
        excerpt = _select_context_excerpt("Πού βρίσκεται το Εθνικό Αρχαιολογικό Μουσείο;", text, 240)
        self.assertIn("Αθήνα", excerpt)
        self.assertLessEqual(len(excerpt), 240)

    def test_multipart_excerpt_reserves_space_for_second_clause(self):
        text = ("Η Python είναι γλώσσα προγραμματισμού. " * 25 + "\n\n"
                + "Το Docker δημιουργήθηκε το 2013 για εκτέλεση containers. " * 10)
        excerpt = _select_context_excerpt("Τι είναι η Python; Πότε δημιουργήθηκε το Docker;", text, 300)
        self.assertIn("Python", excerpt)
        self.assertIn("2013", excerpt)
        self.assertLessEqual(len(excerpt), 300)

    def test_prompt_requires_per_part_evidence_and_requested_language(self):
        request = build_grounded_model_request("Τι είναι η Python;", "[S1] Fixture", 0.1)
        self.assertIn("language of the user's question", request.prompt)
        self.assertIn("each part separately and in order", request.prompt)
        self.assertIn("that part is insufficient", request.prompt)

    def test_shared_words_do_not_stand_in_for_second_entity(self):
        hits = [
            SearchHit(title="Μουσείο Άλφα", url="https://a.example/", snippet="Το μουσείο Άλφα βρίσκεται στην Αθήνα."),
            SearchHit(title="Μουσείο Άλφα", url="https://b.example/", snippet="Το μουσείο Άλφα βρίσκεται στην Αθήνα."),
            SearchHit(title="Μουσείο Βήτα", url="https://c.example/", snippet="Το μουσείο Βήτα βρίσκεται στη Ρόδο."),
        ]
        _, candidates = _build_search_results(hits)
        ranked = _rank_sources("Πού βρίσκεται το μουσείο Άλφα; Πού βρίσκεται το μουσείο Βήτα;", candidates, [], 0)
        self.assertEqual([source.domain for source in ranked[:2]], ["a.example", "c.example"])


class QueryPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_language_override_and_recency_keep_explicit_engine_scope(self):
        for language, expected in (("", "el"), ("auto", "el"), ("en", "en"), ("all", "all")):
            client = AsyncMock()
            client.get.return_value = httpx.Response(200, json={"results": []},
                request=httpx.Request("GET", "http://search-provider:8080/search"))
            manager = AsyncMock()
            manager.__aenter__.return_value = client
            provider = SearxngSearchProvider("http://search-provider:8080", 20,
                categories="auto", language=language, engines="brave,bing,yahoo,brave.news")
            with patch("app.providers.httpx.AsyncClient", return_value=manager):
                await provider.search("Ποιες είναι οι εξελίξεις σήμερα;", 8)
            params = client.get.call_args.kwargs["params"]
            self.assertEqual(params["language"], expected)
            self.assertEqual(params["engines"], "brave,bing,yahoo,brave.news")
            self.assertNotIn("categories", params)
            self.assertEqual(params["q"], "Ποιες είναι οι εξελίξεις σήμερα;")

    async def test_balanced_greek_sources_and_context_under_tight_budget(self):
        search = AsyncMock()
        search.search.return_value = [
            SearchHit(title="Python", url="https://alpha.example/python", snippet="Η Python είναι γλώσσα προγραμματισμού."),
            SearchHit(title="Python οδηγός", url="https://beta.example/python", snippet="Η Python είναι γλώσσα προγραμματισμού."),
            SearchHit(title="Docker", url="https://gamma.example/docker", snippet="Το Docker δημιουργήθηκε το 2013."),
        ]
        fetcher = AsyncMock()
        async def fetch(url):
            body = ("Η Python είναι γλώσσα προγραμματισμού. " if "python" in url
                    else "Το Docker δημιουργήθηκε το 2013. ") * 50
            return FetchDocument(requested_url=url, final_url=url, excerpt=body[:80], content_text=body)
        fetcher.fetch.side_effect = fetch
        bundle, context = await build_grounding_bundle(
            query="Τι είναι η Python; Πότε δημιουργήθηκε το Docker;", search_provider=search,
            fetcher_client=fetcher, search_limit=8, fetch_limit=2,
            source_char_limit=600, total_context_chars=600, preview_chars=100,
        )
        self.assertEqual(search.search.await_count, 3)
        self.assertEqual({source.domain for source in bundle.selected_sources}, {"alpha.example", "gamma.example"})
        self.assertTrue(all(source.context_chars_used > 0 for source in bundle.fetched_sources))
        self.assertLessEqual(bundle.summary.grounding_characters, 600)
        self.assertIn("2013", context)
        self.assertIn("Python", context)

    async def test_disabled_expansion_keeps_one_outbound_query(self):
        search = AsyncMock()
        search.search.return_value = []
        await build_grounding_bundle(query="Τι είναι η Python; Πότε δημιουργήθηκε το Docker;",
            search_provider=search, fetcher_client=AsyncMock(), search_limit=8, fetch_limit=2,
            source_char_limit=300, total_context_chars=600, preview_chars=80, query_expansion_enabled=False)
        self.assertEqual(search.search.await_count, 1)

    async def test_blocked_second_part_keeps_explicit_snippet_evidence(self):
        search = AsyncMock()
        search.search.return_value = [
            SearchHit(title="Python", url="https://alpha.example/python", snippet="Η Python είναι γλώσσα προγραμματισμού."),
            SearchHit(title="Docker", url="https://beta.example/docker", snippet="Το Docker δημιουργήθηκε το 2013."),
        ]
        fetcher = AsyncMock()
        async def fetch(url):
            if "docker" in url:
                raise FetcherRequestError("Blocked fixture", code="upstream_forbidden", upstream_status=403)
            text = "Η Python είναι γλώσσα προγραμματισμού. " * 80
            return FetchDocument(requested_url=url, final_url=url, excerpt=text[:80], content_text=text)
        fetcher.fetch.side_effect = fetch
        bundle, context = await build_grounding_bundle(
            query="Τι είναι η Python; Πότε δημιουργήθηκε το Docker;", search_provider=search,
            fetcher_client=fetcher, search_limit=8, fetch_limit=2, source_char_limit=600,
            total_context_chars=600, preview_chars=100)
        self.assertEqual(bundle.summary.context_mode, "fetched_plus_snippets")
        self.assertIn("2013", context)
        self.assertLessEqual(bundle.summary.grounding_characters, 600)
        self.assertEqual(bundle.summary.failed_sources, 1)
