import os
import json
import unittest
from collections import deque
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi.testclient import TestClient

os.environ["MODEL_PROVIDER"] = "openai_compatible"
os.environ["MODEL_BASE_URL"] = "http://model-backend:8080/v1"
os.environ["MODEL_NAME"] = "test-model"
os.environ["SEARCH_PROVIDER"] = "searxng"
os.environ["SEARCH_BASE_URL"] = "http://search-provider:8080"
os.environ["FETCH_BASE_URL"] = "http://fetcher:8081"

from app.config import Settings
from app.grounding import (
    _build_search_query_variants,
    _select_context_excerpt,
    build_grounded_model_request,
    build_grounding_bundle,
    normalize_grounded_answer,
)
from app.main import app, build_fetcher_client, build_model_provider, build_search_provider
from app.providers import (
    FetchDocument,
    FetcherClient,
    FetcherRequestError,
    ModelDescriptor,
    ModelRuntimeStatus,
    OpenAICompatibleModelProvider,
    OllamaModelProvider,
    ProviderError,
    SearchHit,
    SearxngSearchProvider,
    UnsupportedModelError,
    YacySearchProvider,
)


class MockAsyncClient:
    def __init__(
        self,
        *,
        response: httpx.Response | None = None,
        error: Exception | None = None,
        post_response: httpx.Response | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.post_response = post_response
        self.last_get_params: dict | None = None
        self.last_post_json: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, params: dict | None = None):
        if self.error is not None:
            raise self.error
        self.last_get_params = params
        if self.response is None:
            raise AssertionError("MockAsyncClient requires either a GET response or an error.")
        return self.response

    async def post(self, url: str, json: dict):
        if self.error is not None:
            raise self.error
        self.last_post_json = json
        if self.post_response is None:
            raise AssertionError("MockAsyncClient requires a POST response.")
        return self.post_response


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("app.main.build_model_provider")
    def test_health_endpoint_exposes_provider_summary(self, build_model_provider: AsyncMock) -> None:
        provider = Mock()
        provider.probe_runtime = AsyncMock(return_value=ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        ))
        build_model_provider.return_value = provider

        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["providers"]["model"], "openai_compatible")
        self.assertEqual(payload["providers"]["model_runtime_profile"], "llama.cpp-cuda")
        self.assertTrue(payload["model_runtime"]["ready"])

    @patch("app.main.build_model_provider")
    def test_health_endpoint_reports_degraded_runtime(self, build_model_provider: AsyncMock) -> None:
        provider = Mock()
        provider.probe_runtime = AsyncMock(return_value=ModelRuntimeStatus(
            ready=False,
            reachable=False,
            status="unreachable",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[],
            error="Model runtime request failed: connect failed",
        ))
        build_model_provider.return_value = provider

        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["model_runtime"]["status"], "unreachable")

    def test_provider_endpoint_returns_configured_base_urls(self) -> None:
        response = self.client.get("/api/v1/system/providers")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"]["model_name"], "test-model")
        self.assertTrue(payload["search"]["base_url"].startswith("http://search-provider"))
        self.assertEqual(payload["search"]["categories"], "auto")
        self.assertEqual(payload["search"]["language"], "instance-default")
        self.assertEqual(payload["search"]["time_range"], "none")
        self.assertEqual(
            payload["search"]["engines"],
            "brave,wikipedia,duckduckgo news,google news,reuters",
        )
        self.assertEqual(payload["search"]["preferred_domains"], "wikipedia.org,wikimedia.org")
        self.assertEqual(payload["search"]["preferred_domain_boost"], 14.0)

    @patch("app.main.build_model_provider")
    def test_model_runtime_endpoint_returns_probe_state(self, build_model_provider: AsyncMock) -> None:
        provider = Mock()
        provider.probe_runtime = AsyncMock(return_value=ModelRuntimeStatus(
            ready=False,
            reachable=True,
            status="configured_model_missing",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="other-model", owned_by="local")],
            error="Configured model 'test-model' is not advertised by the runtime.",
        ))
        build_model_provider.return_value = provider

        response = self.client.get("/api/v1/model/runtime")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["status"], "configured_model_missing")
        self.assertEqual(payload["available_models"][0]["id"], "other-model")

    @patch("app.main.build_model_provider")
    def test_chat_endpoint_returns_provider_response(self, build_model_provider: AsyncMock) -> None:
        provider = Mock()
        provider.probe_runtime = AsyncMock(return_value=ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        ))
        provider.select_model = Mock(return_value=type(
            "Selection",
            (),
            {
                "selected_model": "test-model",
                "requested_model": None,
                "selection_source": "configured_default",
                "configured_model": "test-model",
                "model_dump": lambda self=None: {
                    "configured_model": "test-model",
                    "selected_model": "test-model",
                    "requested_model": None,
                    "selection_source": "configured_default",
                },
            },
        )())
        provider.chat = AsyncMock(return_value={
            "model": "test-model",
            "answer": "hello from the model",
            "usage": {"total_tokens": 12},
            "selected_model": "test-model",
        })
        build_model_provider.return_value = provider

        response = self.client.post("/api/v1/model/chat", json={"prompt": "hello"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "hello from the model")
        self.assertEqual(payload["selection"]["selected_model"], "test-model")

    @patch("app.main.build_model_provider")
    def test_chat_endpoint_allows_request_level_model_override(self, build_model_provider: AsyncMock) -> None:
        provider = Mock()
        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[
                ModelDescriptor(id="test-model", owned_by="local"),
                ModelDescriptor(id="alt-model", owned_by="local"),
            ],
            error=None,
        )
        selection = type(
            "Selection",
            (),
            {
                "selected_model": "alt-model",
                "requested_model": "alt-model",
                "selection_source": "request_override",
                "configured_model": "test-model",
                "model_dump": lambda self=None: {
                    "configured_model": "test-model",
                    "selected_model": "alt-model",
                    "requested_model": "alt-model",
                    "selection_source": "request_override",
                },
            },
        )()
        provider.probe_runtime = AsyncMock(return_value=runtime)
        provider.select_model = Mock(return_value=selection)
        provider.chat = AsyncMock(return_value={
            "model": "alt-model",
            "answer": "hello from alt-model",
            "usage": {"total_tokens": 8},
            "selected_model": "alt-model",
        })
        build_model_provider.return_value = provider

        response = self.client.post("/api/v1/model/chat", json={"prompt": "hello", "selected_model": "alt-model"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selection"]["selected_model"], "alt-model")
        self.assertEqual(payload["selection"]["selection_source"], "request_override")
        self.assertEqual(provider.chat.await_args.kwargs["model_name"], "alt-model")

    @patch("app.main.build_model_provider")
    def test_chat_endpoint_rejects_unadvertised_model_override(self, build_model_provider: AsyncMock) -> None:
        provider = Mock()
        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )
        provider.probe_runtime = AsyncMock(return_value=runtime)
        provider.select_model = Mock(side_effect=UnsupportedModelError(
            "Requested model 'missing-model' is not advertised by the runtime."
        ))
        build_model_provider.return_value = provider

        response = self.client.post(
            "/api/v1/model/chat",
            json={"prompt": "hello", "selected_model": "missing-model"},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["detail"]["selection"]["selected_model"], "missing-model")
        self.assertIn("not advertised", payload["detail"]["message"])

    @patch("app.main.build_fetcher_client")
    @patch("app.main.build_search_provider")
    def test_grounding_search_fetch_dedupes_and_reports_partial_failures(
        self,
        build_search_provider: AsyncMock,
        build_fetcher_client: AsyncMock,
    ) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(title="Alpha", url="https://example.com/article", snippet="alpha", engine="mock"),
            SearchHit(title="Alpha Duplicate", url="https://example.com/article?utm=1", snippet="dup", engine="mock"),
            SearchHit(title="Beta", url="https://example.org/post", snippet="beta", engine="mock"),
        ]
        build_search_provider.return_value = search_provider

        fetcher = AsyncMock()
        fetch_results = deque(
            [
                FetchDocument(
                    requested_url="https://example.com/article",
                    final_url="https://example.com/article",
                    title="Alpha Title",
                    excerpt="Alpha excerpt",
                    content_text="Alpha content " * 50,
                    content_char_count=700,
                    word_count=100,
                    content_type="text/html",
                ),
                ProviderError("Fetch request failed: fetch failed"),
            ]
        )

        async def fetch_side_effect(url: str):
            value = fetch_results.popleft()
            if isinstance(value, Exception):
                raise value
            return value

        fetcher.fetch.side_effect = fetch_side_effect
        build_fetcher_client.return_value = fetcher

        response = self.client.post("/api/v1/grounding/search-fetch", json={"query": "privacy", "fetch_limit": 2})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["search_results"], 3)
        self.assertEqual(payload["summary"]["unique_search_results"], 2)
        self.assertEqual(payload["summary"]["fetched_sources"], 1)
        self.assertEqual(payload["summary"]["failed_sources"], 1)
        self.assertEqual(payload["search_results"][1]["status"], "duplicate")
        self.assertEqual(payload["errors"][0]["stage"], "fetch")

    @patch("app.main.build_model_provider")
    @patch("app.main.build_fetcher_client")
    @patch("app.main.build_search_provider")
    def test_grounding_answer_passes_source_text_to_model(
        self,
        build_search_provider: AsyncMock,
        build_fetcher_client: AsyncMock,
        build_model_provider: AsyncMock,
    ) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(title="Alpha", url="https://example.com/article", snippet="alpha", engine="mock")
        ]
        build_search_provider.return_value = search_provider

        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchDocument(
            requested_url="https://example.com/article",
            final_url="https://example.com/article",
            title="Alpha Title",
            excerpt="Alpha excerpt",
            content_text="Alpha content for the grounding path.",
            content_char_count=37,
            word_count=6,
            content_type="text/html",
        )
        build_fetcher_client.return_value = fetcher

        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )
        selection = type(
            "Selection",
            (),
            {
                "selected_model": "test-model",
                "requested_model": None,
                "selection_source": "configured_default",
                "configured_model": "test-model",
                "model_dump": lambda self=None: {
                    "configured_model": "test-model",
                    "selected_model": "test-model",
                    "requested_model": None,
                    "selection_source": "configured_default",
                },
            },
        )()
        model_provider = Mock()
        model_provider.probe_runtime = AsyncMock(return_value=runtime)
        model_provider.select_model = Mock(return_value=selection)
        model_provider.chat = AsyncMock(return_value={
            "model": "test-model",
            "answer": "Grounded answer [S1]",
            "usage": {"total_tokens": 42},
            "selected_model": "test-model",
        })
        build_model_provider.return_value = model_provider

        response = self.client.post("/api/v1/grounding/answer", json={"query": "What does Alpha say?"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer_status"], "grounded")
        self.assertEqual(payload["answer"], "Grounded answer [S1]")
        self.assertEqual(payload["selection"]["selected_model"], "test-model")
        prompt = model_provider.chat.await_args.kwargs["prompt"]
        self.assertIn("[S1]", prompt)
        self.assertIn("Alpha content for the grounding path.", prompt)

    @patch("app.main.build_model_provider")
    @patch("app.main.build_fetcher_client")
    @patch("app.main.build_search_provider")
    def test_grounding_answer_passes_additional_system_instructions(
        self,
        build_search_provider: AsyncMock,
        build_fetcher_client: AsyncMock,
        build_model_provider: AsyncMock,
    ) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(title="Alpha", url="https://example.com/article", snippet="alpha", engine="mock")
        ]
        build_search_provider.return_value = search_provider

        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchDocument(
            requested_url="https://example.com/article",
            final_url="https://example.com/article",
            title="Alpha Title",
            excerpt="Alpha excerpt",
            content_text="Alpha content for the grounding path.",
            content_char_count=37,
            word_count=6,
            content_type="text/html",
        )
        build_fetcher_client.return_value = fetcher

        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )
        selection = type(
            "Selection",
            (),
            {
                "selected_model": "test-model",
                "requested_model": None,
                "selection_source": "configured_default",
                "configured_model": "test-model",
                "model_dump": lambda self=None: {
                    "configured_model": "test-model",
                    "selected_model": "test-model",
                    "requested_model": None,
                    "selection_source": "configured_default",
                },
            },
        )()
        model_provider = Mock()
        model_provider.probe_runtime = AsyncMock(return_value=runtime)
        model_provider.select_model = Mock(return_value=selection)
        model_provider.chat = AsyncMock(return_value={
            "model": "test-model",
            "answer": "Grounded answer [S1]",
            "usage": {"total_tokens": 42},
            "selected_model": "test-model",
        })
        build_model_provider.return_value = model_provider

        response = self.client.post(
            "/api/v1/grounding/answer",
            json={
                "query": "What does Alpha say?",
                "system_prompt": "Do not guess and always cite sources.",
            },
        )
        self.assertEqual(response.status_code, 200)
        system_prompt = model_provider.chat.await_args.kwargs["system_prompt"]
        self.assertIn("Do not guess and always cite sources.", system_prompt)

    @patch("app.main.build_model_provider")
    @patch("app.main.build_fetcher_client")
    @patch("app.main.build_search_provider")
    def test_grounding_answer_normalizes_grouped_citations(
        self,
        build_search_provider: AsyncMock,
        build_fetcher_client: AsyncMock,
        build_model_provider: AsyncMock,
    ) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(title="Alpha", url="https://example.com/article-a", snippet="alpha", engine="mock"),
            SearchHit(title="Bravo", url="https://example.com/article-b", snippet="bravo", engine="mock"),
        ]
        build_search_provider.return_value = search_provider

        fetcher = AsyncMock()

        async def fetch_side_effect(url: str) -> FetchDocument:
            label = "Alpha" if url.endswith("article-a") else "Bravo"
            return FetchDocument(
                requested_url=url,
                final_url=url,
                title=f"{label} Title",
                excerpt=f"{label} excerpt",
                content_text=f"{label} content for the grounding path.",
                content_char_count=37,
                word_count=6,
                content_type="text/html",
            )

        fetcher.fetch.side_effect = fetch_side_effect
        build_fetcher_client.return_value = fetcher

        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )
        selection = type(
            "Selection",
            (),
            {
                "selected_model": "test-model",
                "requested_model": None,
                "selection_source": "configured_default",
                "configured_model": "test-model",
                "model_dump": lambda self=None: {
                    "configured_model": "test-model",
                    "selected_model": "test-model",
                    "requested_model": None,
                    "selection_source": "configured_default",
                },
            },
        )()
        model_provider = Mock()
        model_provider.probe_runtime = AsyncMock(return_value=runtime)
        model_provider.select_model = Mock(return_value=selection)
        model_provider.chat = AsyncMock(return_value={
            "model": "test-model",
            "answer": "The answer is February 28, 2026 [S1, S2].",
            "usage": {"total_tokens": 42},
            "selected_model": "test-model",
        })
        build_model_provider.return_value = model_provider

        response = self.client.post("/api/v1/grounding/answer", json={"query": "When did it happen?"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "The answer is February 28, 2026 [S1][S2].")

    @patch("app.main.build_model_provider")
    @patch("app.main.build_fetcher_client")
    @patch("app.main.build_search_provider")
    def test_grounding_answer_uses_snippet_fallback_when_fetches_fail(
        self,
        build_search_provider: AsyncMock,
        build_fetcher_client: AsyncMock,
        build_model_provider: AsyncMock,
    ) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Timeline",
                url="https://example.com/timeline",
                snippet="The first reported strike happened on February 28, 2026.",
                engine="mock",
            )
        ]
        build_search_provider.return_value = search_provider

        fetcher = AsyncMock()
        fetcher.fetch.side_effect = ProviderError("Fetch request failed: blocked")
        build_fetcher_client.return_value = fetcher

        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )
        selection = type(
            "Selection",
            (),
            {
                "selected_model": "test-model",
                "requested_model": None,
                "selection_source": "configured_default",
                "configured_model": "test-model",
                "model_dump": lambda self=None: {
                    "configured_model": "test-model",
                    "selected_model": "test-model",
                    "requested_model": None,
                    "selection_source": "configured_default",
                },
            },
        )()
        model_provider = Mock()
        model_provider.probe_runtime = AsyncMock(return_value=runtime)
        model_provider.select_model = Mock(return_value=selection)
        model_provider.chat = AsyncMock(return_value={
            "model": "test-model",
            "answer": "The first reported strike was on February 28, 2026. [S1]",
            "usage": {"total_tokens": 24},
            "selected_model": "test-model",
        })
        build_model_provider.return_value = model_provider

        response = self.client.post("/api/v1/grounding/answer", json={"query": "When was the first strike?"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer_status"], "snippet_grounded")
        self.assertEqual(payload["grounding"]["summary"]["context_mode"], "search_snippets")
        prompt = model_provider.chat.await_args.kwargs["prompt"]
        self.assertIn("Search result snippets:", prompt)
        self.assertIn("February 28, 2026", prompt)

    @patch("app.main.build_model_provider")
    @patch("app.main.build_fetcher_client")
    @patch("app.main.build_search_provider")
    def test_grounding_answer_uses_hybrid_context_when_some_fetches_fail(
        self,
        build_search_provider: AsyncMock,
        build_fetcher_client: AsyncMock,
        build_model_provider: AsyncMock,
    ) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Fetched report",
                url="https://example.com/fetched",
                snippet="Fetched report snippet.",
                engine="mock",
            ),
            SearchHit(
                title="Blocked report",
                url="https://example.com/blocked",
                snippet="Negotiations may resume if the naval blockade ends.",
                engine="mock",
            ),
        ]
        build_search_provider.return_value = search_provider

        fetcher = AsyncMock()

        async def fetch_side_effect(url: str):
            if url.endswith("/blocked"):
                raise ProviderError("Fetch request failed: blocked")

            return FetchDocument(
                requested_url=url,
                final_url=url,
                title="Fetched report",
                excerpt="Fetched report excerpt.",
                content_text="The Strait of Hormuz remains contested after vessel attacks.",
                content_char_count=59,
                word_count=9,
                content_type="text/html",
            )

        fetcher.fetch.side_effect = fetch_side_effect
        build_fetcher_client.return_value = fetcher

        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )
        selection = type(
            "Selection",
            (),
            {
                "selected_model": "test-model",
                "requested_model": None,
                "selection_source": "configured_default",
                "configured_model": "test-model",
                "model_dump": lambda self=None: {
                    "configured_model": "test-model",
                    "selected_model": "test-model",
                    "requested_model": None,
                    "selection_source": "configured_default",
                },
            },
        )()
        model_provider = Mock()
        model_provider.probe_runtime = AsyncMock(return_value=runtime)
        model_provider.select_model = Mock(return_value=selection)
        model_provider.chat = AsyncMock(return_value={
            "model": "test-model",
            "answer": "The Strait remains contested while talks are conditional. [S1][S2]",
            "usage": {"total_tokens": 42},
            "selected_model": "test-model",
        })
        build_model_provider.return_value = model_provider

        response = self.client.post(
            "/api/v1/grounding/answer",
            json={"query": "Is the strait open and are talks resuming?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["grounding"]["summary"]["context_mode"], "fetched_plus_snippets")
        prompt = model_provider.chat.await_args.kwargs["prompt"]
        system_prompt = model_provider.chat.await_args.kwargs["system_prompt"]
        self.assertIn("Grounded sources and snippet fallbacks:", prompt)
        self.assertIn("Source text:", prompt)
        self.assertIn("Search snippet fallback:", prompt)
        self.assertIn("Prefer fetched article text", system_prompt)

    @patch("app.main.build_model_provider")
    def test_grounding_answer_rejects_unadvertised_model_override(self, build_model_provider: AsyncMock) -> None:
        provider = Mock()
        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )
        provider.probe_runtime = AsyncMock(return_value=runtime)
        provider.select_model = Mock(side_effect=UnsupportedModelError(
            "Requested model 'missing-model' is not advertised by the runtime."
        ))
        build_model_provider.return_value = provider

        response = self.client.post(
            "/api/v1/grounding/answer",
            json={"query": "What does Alpha say?", "selected_model": "missing-model"},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["detail"]["selection"]["selected_model"], "missing-model")


class ProviderFactoryTests(unittest.TestCase):
    def test_build_model_provider_selects_ollama_adapter(self) -> None:
        settings = Settings(
            MODEL_PROVIDER="ollama",
            MODEL_BASE_URL="http://ollama:11434/api",
            MODEL_NAME="qwen2.5:7b",
        )

        provider = build_model_provider(settings)
        self.assertIsInstance(provider, OllamaModelProvider)

    def test_build_search_provider_selects_yacy_adapter(self) -> None:
        settings = Settings(
            SEARCH_PROVIDER="yacy",
            SEARCH_BASE_URL="http://yacy-search:8090",
        )

        provider = build_search_provider(settings)
        self.assertIsInstance(provider, YacySearchProvider)

    def test_build_fetcher_client_uses_dedicated_fetcher_timeout(self) -> None:
        settings = Settings(
            FETCH_BASE_URL="http://fetcher:8081",
            FETCH_REQUEST_TIMEOUT_SECONDS=20,
            FETCHER_CLIENT_TIMEOUT_SECONDS=35,
        )

        client = build_fetcher_client(settings)
        self.assertIsInstance(client, FetcherClient)
        self.assertEqual(client.timeout_seconds, 35.0)


class ProviderClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetcher_client_raises_structured_fetcher_request_error(self) -> None:
        client = FetcherClient(base_url="http://fetcher:8081", timeout_seconds=20.0)
        response = httpx.Response(
            502,
            request=httpx.Request("POST", "http://fetcher:8081/api/v1/fetch"),
            content=json.dumps(
                {
                    "detail": {
                        "message": "Remote site denied automated fetching under its robot policy.",
                        "code": "blocked_by_remote_policy",
                        "upstream_status": 403,
                        "retryable": False,
                    }
                }
            ).encode("utf-8"),
        )

        with patch("app.providers.httpx.AsyncClient", return_value=MockAsyncClient(post_response=response)):
            with self.assertRaises(FetcherRequestError) as context:
                await client.fetch("https://example.com/article")

        self.assertEqual(str(context.exception), "Remote site denied automated fetching under its robot policy.")
        self.assertEqual(context.exception.code, "blocked_by_remote_policy")
        self.assertEqual(context.exception.upstream_status, 403)
        self.assertFalse(context.exception.retryable)

    async def test_fetcher_client_reports_backend_timeout_with_non_blank_message(self) -> None:
        client = FetcherClient(base_url="http://fetcher:8081", timeout_seconds=20.0)

        with patch(
            "app.providers.httpx.AsyncClient",
            return_value=MockAsyncClient(error=httpx.ReadTimeout("")),
        ):
            with self.assertRaises(ProviderError) as context:
                await client.fetch("https://example.com/article")

        self.assertEqual(
            str(context.exception),
            "Fetcher service timed out before it returned a response: ReadTimeout",
        )


class ModelProviderProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_probe_runtime_reports_unreachable_runtime(self) -> None:
        provider = OpenAICompatibleModelProvider(
            base_url="http://model-backend:8080/v1",
            model_name="test-model",
            timeout_seconds=90.0,
            probe_timeout_seconds=5.0,
        )
        with patch(
            "app.providers.httpx.AsyncClient",
            return_value=MockAsyncClient(error=httpx.ConnectError("connect failed")),
        ):
            status = await provider.probe_runtime()

        self.assertFalse(status.ready)
        self.assertFalse(status.reachable)
        self.assertEqual(status.status, "unreachable")

    async def test_probe_runtime_reports_invalid_response(self) -> None:
        provider = OpenAICompatibleModelProvider(
            base_url="http://model-backend:8080/v1",
            model_name="test-model",
            timeout_seconds=90.0,
            probe_timeout_seconds=5.0,
        )
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://model-backend:8080/v1/models"),
            content=b"not-json",
        )
        with patch("app.providers.httpx.AsyncClient", return_value=MockAsyncClient(response=response)):
            status = await provider.probe_runtime()

        self.assertFalse(status.ready)
        self.assertTrue(status.reachable)
        self.assertEqual(status.status, "invalid_response")

    async def test_select_model_allows_request_override_when_runtime_advertises_it(self) -> None:
        provider = OpenAICompatibleModelProvider(
            base_url="http://model-backend:8080/v1",
            model_name="test-model",
            timeout_seconds=90.0,
            probe_timeout_seconds=5.0,
        )
        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[
                ModelDescriptor(id="test-model", owned_by="local"),
                ModelDescriptor(id="alt-model", owned_by="local"),
            ],
            error=None,
        )

        selection = provider.select_model("alt-model", runtime_status=runtime)
        self.assertEqual(selection.selected_model, "alt-model")
        self.assertEqual(selection.selection_source, "request_override")

    async def test_select_model_rejects_unadvertised_override(self) -> None:
        provider = OpenAICompatibleModelProvider(
            base_url="http://model-backend:8080/v1",
            model_name="test-model",
            timeout_seconds=90.0,
            probe_timeout_seconds=5.0,
        )
        runtime = ModelRuntimeStatus(
            ready=True,
            reachable=True,
            status="ready",
            configured_model="test-model",
            checked_url="http://model-backend:8080/v1/models",
            available_models=[ModelDescriptor(id="test-model", owned_by="local")],
            error=None,
        )

        with self.assertRaises(UnsupportedModelError):
            provider.select_model("missing-model", runtime_status=runtime)

    async def test_ollama_probe_runtime_reports_ready_models(self) -> None:
        provider = OllamaModelProvider(
            base_url="http://ollama:11434/api",
            model_name="qwen2.5:7b",
            timeout_seconds=90.0,
            probe_timeout_seconds=5.0,
        )
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://ollama:11434/api/tags"),
            content=json.dumps(
                {
                    "models": [
                        {
                            "name": "qwen2.5:7b",
                            "model": "qwen2.5:7b",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        with patch("app.providers.httpx.AsyncClient", return_value=MockAsyncClient(response=response)):
            status = await provider.probe_runtime()

        self.assertTrue(status.ready)
        self.assertEqual(status.available_models[0].id, "qwen2.5:7b")

    async def test_ollama_chat_uses_native_endpoint_and_builds_usage(self) -> None:
        provider = OllamaModelProvider(
            base_url="http://ollama:11434/api",
            model_name="qwen2.5:7b",
            timeout_seconds=90.0,
            probe_timeout_seconds=5.0,
        )
        response = httpx.Response(
            200,
            request=httpx.Request("POST", "http://ollama:11434/api/chat"),
            content=json.dumps(
                {
                    "model": "alt-model:latest",
                    "message": {"role": "assistant", "content": "hello from ollama"},
                    "prompt_eval_count": 12,
                    "eval_count": 8,
                }
            ).encode("utf-8"),
        )
        client = MockAsyncClient(post_response=response)
        with patch("app.providers.httpx.AsyncClient", return_value=client):
            result = await provider.chat(
                prompt="hello",
                system_prompt="be concise",
                temperature=0.3,
                model_name="alt-model:latest",
            )

        self.assertEqual(result["answer"], "hello from ollama")
        self.assertEqual(result["usage"]["prompt_tokens"], 12)
        self.assertEqual(result["usage"]["completion_tokens"], 8)
        self.assertEqual(result["usage"]["total_tokens"], 20)
        self.assertEqual(client.last_post_json["model"], "alt-model:latest")
        self.assertFalse(client.last_post_json["stream"])
        self.assertEqual(client.last_post_json["options"]["temperature"], 0.3)


class GroundingPipelineTests(unittest.IsolatedAsyncioTestCase):
    def test_multi_part_query_builds_original_and_clause_variants(self) -> None:
        variants = _build_search_query_variants(
            "Are the Straits of Hormuz open and what is the current state of the talks?"
        )

        self.assertEqual(
            variants,
            [
                "Are the Straits of Hormuz open and what is the current state of the talks?",
                "Are the Straits of Hormuz open",
                "what is the current state of the talks",
            ],
        )

    async def test_multi_part_search_keeps_successful_variants_when_one_fails(self) -> None:
        search_provider = AsyncMock()

        async def search_side_effect(query: str, limit: int):
            if query.startswith("what is the current"):
                raise ProviderError("SearXNG returned HTTP 503")
            return [
                SearchHit(
                    title="Hormuz status",
                    url=f"https://example.org/{'open' if query.startswith('Are') else 'combined'}",
                    snippet="The Strait of Hormuz is open according to the latest report.",
                    engine="mock",
                )
            ]

        search_provider.search.side_effect = search_side_effect
        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchDocument(
            requested_url="https://example.org/open",
            final_url="https://example.org/open",
            title="Hormuz status",
            excerpt="The strait is open.",
            content_text="The Strait of Hormuz is open according to the latest report.",
            content_char_count=74,
            word_count=11,
            content_type="text/html",
        )

        bundle, context = await build_grounding_bundle(
            query="Are the Straits of Hormuz open and what is the current state of the talks?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=3,
            fetch_limit=1,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual(search_provider.search.await_count, 3)
        self.assertEqual(bundle.summary.search_failures, 1)
        self.assertEqual(bundle.summary.failed_sources, 0)
        self.assertEqual(bundle.errors[0].code, "search_variant_failed")
        self.assertIn("Hormuz is open", context)

    async def test_grounding_bundle_ranks_sources_and_retries_after_fetch_failures(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(title="Market Wrap", url="https://alpha.example/news", snippet="Stocks and commodities", engine="mock"),
            SearchHit(
                title="Iran attack timeline 2026",
                url="https://bravo.example/timeline",
                snippet="Israel and U.S. strike timeline coverage",
                engine="mock",
            ),
            SearchHit(
                title="US and Israel strike Iran: first reported date",
                url="https://charlie.example/report",
                snippet="First reported attack date and sequence",
                engine="mock",
            ),
            SearchHit(
                title="Reuters live updates on Iran strike",
                url="https://delta.example/live",
                snippet="Israel U.S. operation date and live updates",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()

        async def fetch_side_effect(url: str):
            if url == "https://bravo.example/timeline":
                raise ProviderError("Fetch request failed: source blocked")
            if url == "https://charlie.example/report":
                return FetchDocument(
                    requested_url=url,
                    final_url=url,
                    title="First reported date",
                    excerpt="Coverage of the first reported date.",
                    content_text="The first reported date was described in the article.",
                    content_char_count=54,
                    word_count=10,
                    content_type="text/html",
                )
            if url == "https://delta.example/live":
                return FetchDocument(
                    requested_url=url,
                    final_url=url,
                    title="Live updates",
                    excerpt="Live updates on the operation date.",
                    content_text="Live coverage repeated the reported date and cited officials.",
                    content_char_count=63,
                    word_count=10,
                    content_type="text/html",
                )
            return FetchDocument(
                requested_url=url,
                final_url=url,
                title="Fallback article",
                excerpt="Fallback",
                content_text="Unrelated fallback text.",
                content_char_count=23,
                word_count=3,
                content_type="text/html",
            )

        fetcher.fetch.side_effect = fetch_side_effect

        bundle, context = await build_grounding_bundle(
            query="When did the first Israel USA attack on Iran take place in 2026?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=4,
            fetch_limit=2,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual([item.source_id for item in bundle.selected_sources], ["S2", "S3", "S4"])
        self.assertEqual([item.source_id for item in bundle.fetched_sources], ["S3", "S4"])
        self.assertEqual(bundle.summary.selected_sources, 3)
        self.assertEqual(bundle.summary.fetched_sources, 2)
        self.assertEqual(bundle.summary.failed_sources, 1)
        self.assertEqual(bundle.summary.context_mode, "fetched_plus_snippets")
        self.assertEqual(bundle.search_results[0].status, "unselected")
        self.assertEqual(bundle.search_results[1].status, "selected")
        self.assertIn("[S3]", context)
        self.assertIn("[S4]", context)
        self.assertIn("Search snippet fallback:", context)

    async def test_grounding_bundle_prefers_configured_domains_when_relevant(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Explainer",
                url="https://alpha.example/explainer",
                snippet="Overview of a twelve day conflict and regional reaction.",
                engine="mock",
            ),
            SearchHit(
                title="Twelve-Day War - Wikipedia",
                url="https://en.wikipedia.org/wiki/Twelve-Day_War",
                snippet="The Twelve-Day War was an armed conflict involving Israel, Iran, and the United States.",
                engine="wikipedia",
            ),
            SearchHit(
                title="Liveblog",
                url="https://bravo.example/liveblog",
                snippet="Rolling updates on the same conflict.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchDocument(
            requested_url="https://en.wikipedia.org/wiki/Twelve-Day_War",
            final_url="https://en.wikipedia.org/wiki/Twelve-Day_War",
            title="Twelve-Day War",
            excerpt="Wikipedia summary",
            content_text="Wikipedia-backed article text.",
            content_char_count=30,
            word_count=4,
            content_type="text/html",
            retrieval_method="wikimedia_parse_api",
        )

        bundle, context = await build_grounding_bundle(
            query="What is the Twelve-Day War?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=3,
            fetch_limit=1,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
            preferred_domains="wikipedia.org,wikimedia.org",
            preferred_domain_boost=14.0,
        )

        self.assertEqual(bundle.selected_sources[0].domain, "en.wikipedia.org")
        self.assertEqual(bundle.fetched_sources[0].retrieval_method, "wikimedia_parse_api")
        self.assertIn("[S2]", context)

    async def test_grounding_bundle_does_not_overweight_preferred_domains_for_non_definitional_queries(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Twelve-Day War - Wikipedia",
                url="https://en.wikipedia.org/wiki/Twelve-Day_War",
                snippet="Background on the wider conflict.",
                engine="wikipedia",
            ),
            SearchHit(
                title="First reported strike date",
                url="https://alpha.example/report",
                snippet="On February 28, 2026, the first reported strike began according to officials.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()
        fetcher.fetch.return_value = FetchDocument(
            requested_url="https://alpha.example/report",
            final_url="https://alpha.example/report",
            title="First reported strike date",
            excerpt="Report excerpt",
            content_text="On February 28, 2026, the first reported strike began according to officials.",
            content_char_count=73,
            word_count=12,
            content_type="text/html",
            retrieval_method="direct_html",
        )

        bundle, context = await build_grounding_bundle(
            query="When did the first reported strike begin?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=2,
            fetch_limit=1,
            source_char_limit=320,
            total_context_chars=640,
            preview_chars=160,
            preferred_domains="wikipedia.org,wikimedia.org",
            preferred_domain_boost=14.0,
        )

        self.assertEqual(bundle.selected_sources[0].domain, "alpha.example")
        self.assertIn("February 28, 2026", context)

    async def test_grounding_bundle_falls_back_to_search_snippets(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Timeline",
                url="https://example.com/timeline",
                snippet="The first reported strike happened on February 28, 2026.",
                engine="mock",
            ),
            SearchHit(
                title="Background",
                url="https://example.org/background",
                snippet="Israel and the United States launched attacks on Iran.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()
        fetcher.fetch.side_effect = ProviderError("Fetch request failed: blocked")

        bundle, context = await build_grounding_bundle(
            query="When did the first strike happen?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=2,
            fetch_limit=2,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual(bundle.summary.context_mode, "search_snippets")
        self.assertEqual(bundle.summary.fetched_sources, 0)
        self.assertEqual(bundle.summary.failed_sources, 2)
        self.assertIn("Search snippet:", context)
        self.assertIn("February 28, 2026", context)

    async def test_grounding_bundle_filters_off_topic_snippet_only_fallback_for_status_query(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Hormuz blockade update",
                url="https://alpha.example/hormuz",
                snippet="The Strait of Hormuz remains closed while Iran and the United States have not agreed on a date for renewed talks.",
                engine="mock",
            ),
            SearchHit(
                title="Regional talks update",
                url="https://bravo.example/talks",
                snippet="Lebanon and Israel continued separate peace talks after overnight shelling.",
                engine="mock",
            ),
            SearchHit(
                title="Background",
                url="https://charlie.example/background",
                snippet="Background context on the wider regional conflict.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()
        fetcher.fetch.side_effect = ProviderError("Fetch request failed: blocked")

        bundle, context = await build_grounding_bundle(
            query="Are the Straits of Hormuz open and what is the current state of the Iranian-American peace talks?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=3,
            fetch_limit=2,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual(bundle.summary.context_mode, "search_snippets")
        self.assertIn("Strait of Hormuz remains closed", context)
        self.assertNotIn("Lebanon and Israel", context)
        self.assertNotIn("wider regional conflict", context)

    async def test_grounding_bundle_retries_after_thin_content(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Primary report",
                url="https://alpha.example/report",
                snippet="Primary report with the expected timeline.",
                engine="mock",
            ),
            SearchHit(
                title="Secondary report",
                url="https://bravo.example/report",
                snippet="Secondary report confirming the same date.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()

        async def fetch_side_effect(url: str):
            if url == "https://alpha.example/report":
                return FetchDocument(
                    requested_url=url,
                    final_url=url,
                    title="Thin shell",
                    excerpt="Thin shell.",
                    content_text="Login required.",
                    content_char_count=15,
                    word_count=2,
                    content_type="text/html",
                    retrieval_method="direct_html",
                    content_quality="thin",
                    warnings=["Extracted page content looks thin and may be a paywall shell."],
                )

            return FetchDocument(
                requested_url=url,
                final_url=url,
                title="Usable report",
                excerpt="Usable report excerpt.",
                content_text="The article text clearly states the first reported strike date and supporting details.",
                content_char_count=82,
                word_count=13,
                content_type="text/html",
                retrieval_method="direct_html",
                content_quality="usable",
                warnings=[],
            )

        fetcher.fetch.side_effect = fetch_side_effect

        bundle, context = await build_grounding_bundle(
            query="When was the first reported strike?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=2,
            fetch_limit=1,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual(bundle.summary.fetched_sources, 1)
        self.assertEqual(bundle.summary.failed_sources, 1)
        self.assertEqual(bundle.summary.context_mode, "fetched_plus_snippets")
        self.assertEqual(bundle.errors[0].code, "content_too_thin")
        self.assertFalse(bundle.errors[0].retryable)
        self.assertEqual(bundle.fetched_sources[0].source_id, "S2")
        self.assertEqual(bundle.fetched_sources[0].retrieval_method, "direct_html")
        self.assertEqual(bundle.fetched_sources[0].content_quality, "usable")
        self.assertIn("[S2]", context)
        self.assertIn("Search snippet fallback:", context)

    async def test_grounding_bundle_uses_hybrid_context_when_failed_sources_have_snippets(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Fetched report",
                url="https://alpha.example/report",
                snippet="Fetched report snippet.",
                engine="mock",
            ),
            SearchHit(
                title="Blocked update",
                url="https://bravo.example/update",
                snippet="Iran says talks can resume after the blockade ends.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()

        async def fetch_side_effect(url: str):
            if url == "https://bravo.example/update":
                raise FetcherRequestError(
                    "Remote site denied the fetch request.",
                    code="upstream_forbidden",
                    upstream_status=403,
                    retryable=False,
                )

            return FetchDocument(
                requested_url=url,
                final_url=url,
                title="Fetched report",
                excerpt="Fetched report excerpt.",
                content_text="The Strait of Hormuz remains contested after vessel attacks.",
                content_char_count=59,
                word_count=9,
                content_type="text/html",
                retrieval_method="direct_html",
                content_quality="usable",
                warnings=[],
            )

        fetcher.fetch.side_effect = fetch_side_effect

        bundle, context = await build_grounding_bundle(
            query="Is the strait open and are talks resuming?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=2,
            fetch_limit=2,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual(bundle.summary.context_mode, "fetched_plus_snippets")
        self.assertEqual(bundle.summary.fetched_sources, 1)
        self.assertEqual(bundle.summary.failed_sources, 1)
        self.assertIn("Source text:", context)
        self.assertIn("Search snippet fallback:", context)
        self.assertIn("Iran says talks can resume", context)

    async def test_grounding_bundle_limits_hybrid_snippet_fallback_to_top_relevant_failed_sources(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Fetched report",
                url="https://alpha.example/report",
                snippet="Fetched report snippet.",
                engine="mock",
            ),
            SearchHit(
                title="Specific timeline",
                url="https://bravo.example/timeline",
                snippet="The first reported strike began on February 28, 2026, according to witnesses.",
                engine="mock",
            ),
            SearchHit(
                title="Live updates",
                url="https://charlie.example/live",
                snippet="Rolling updates and reactions from throughout the region.",
                engine="mock",
            ),
            SearchHit(
                title="Background",
                url="https://delta.example/background",
                snippet="Regional background and long-term context.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()

        async def fetch_side_effect(url: str):
            if url == "https://alpha.example/report":
                return FetchDocument(
                    requested_url=url,
                    final_url=url,
                    title="Fetched report",
                    excerpt="Fetched report excerpt.",
                    content_text="Officials say the first strike date remains disputed pending review.",
                    content_char_count=66,
                    word_count=11,
                    content_type="text/html",
                    retrieval_method="direct_html",
                    content_quality="usable",
                    warnings=[],
                )
            raise ProviderError("Fetch request failed: blocked")

        fetcher.fetch.side_effect = fetch_side_effect

        bundle, context = await build_grounding_bundle(
            query="When did the first reported strike begin?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=4,
            fetch_limit=2,
            source_char_limit=320,
            total_context_chars=900,
            preview_chars=160,
        )

        self.assertEqual(bundle.summary.context_mode, "fetched_plus_snippets")
        self.assertIn("February 28, 2026", context)
        self.assertNotIn("Regional background and long-term context.", context)

    async def test_grounding_bundle_skips_later_candidates_from_blocked_domain(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Primary timeline",
                url="https://blocked.example/timeline",
                snippet="First report from blocked domain.",
                engine="mock",
            ),
            SearchHit(
                title="Confirming report",
                url="https://usable.example/confirming-report",
                snippet="Second source with the same date.",
                engine="mock",
            ),
            SearchHit(
                title="Blocked follow-up",
                url="https://blocked.example/follow-up",
                snippet="Another blocked result from the same domain.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()
        attempted_urls: list[str] = []

        async def fetch_side_effect(url: str):
            attempted_urls.append(url)
            if url == "https://blocked.example/timeline":
                raise FetcherRequestError(
                    "Remote site denied automated fetching under its robot policy.",
                    code="blocked_by_remote_policy",
                    upstream_status=403,
                    retryable=False,
                )

            return FetchDocument(
                requested_url=url,
                final_url=url,
                title="Usable report",
                excerpt="Usable report excerpt.",
                content_text="The article confirms the date and surrounding context in readable text.",
                content_char_count=71,
                word_count=11,
                content_type="text/html",
                retrieval_method="direct_html",
                content_quality="usable",
                warnings=[],
            )

        fetcher.fetch.side_effect = fetch_side_effect

        bundle, context = await build_grounding_bundle(
            query="When was the first reported strike?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=3,
            fetch_limit=2,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual(
            attempted_urls,
            [
                "https://blocked.example/timeline",
                "https://usable.example/confirming-report",
            ],
        )
        self.assertEqual(bundle.summary.selected_sources, 2)
        self.assertEqual(bundle.summary.failed_sources, 1)
        self.assertEqual(bundle.errors[0].code, "blocked_by_remote_policy")
        self.assertEqual(bundle.errors[0].upstream_status, 403)
        self.assertFalse(bundle.errors[0].retryable)
        self.assertEqual(bundle.search_results[2].status, "unselected")
        self.assertIn("[S2]", context)

    async def test_grounding_bundle_prefers_same_domain_non_live_candidate_for_current_events_query(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Live updates: Strait of Hormuz blockade",
                url="https://example.com/live/hormuz",
                snippet="Live updates on the blockade and peace talks.",
                engine="mock",
            ),
            SearchHit(
                title="What to know: Strait of Hormuz blockade and Iran-U.S. talks",
                url="https://example.com/analysis/hormuz-talks",
                snippet="Explainer on whether the strait is open and whether talks are resuming.",
                engine="mock",
            ),
            SearchHit(
                title="Other publisher update",
                url="https://other.example/update",
                snippet="Another update on the same events.",
                engine="mock",
            ),
        ]

        fetcher = AsyncMock()

        async def fetch_side_effect(url: str):
            if url == "https://example.com/analysis/hormuz-talks":
                return FetchDocument(
                    requested_url=url,
                    final_url=url,
                    title="What to know",
                    excerpt="Explainer excerpt.",
                    content_text="The Strait of Hormuz is not open, and no date has been agreed for renewed Iran-U.S. talks.",
                    content_char_count=90,
                    word_count=16,
                    content_type="text/html",
                    retrieval_method="direct_html",
                    content_quality="usable",
                    warnings=[],
                )
            raise ProviderError("Fetch request failed: blocked")

        fetcher.fetch.side_effect = fetch_side_effect

        bundle, context = await build_grounding_bundle(
            query="Are the Straits of Hormuz open and what is the current state of the Iranian-American peace talks?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=3,
            fetch_limit=1,
            source_char_limit=400,
            total_context_chars=800,
            preview_chars=160,
        )

        self.assertEqual(bundle.selected_sources[0].source_id, "S2")
        self.assertEqual(bundle.fetched_sources[0].source_id, "S2")
        self.assertIn("Strait of Hormuz is not open", context)

    async def test_grounding_bundle_selects_query_relevant_excerpt_from_long_document(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="War timeline",
                url="https://example.com/timeline",
                snippet="Timeline overview.",
                engine="mock",
            )
        ]

        fetcher = AsyncMock()
        leading_background = "Background context about regional tensions and general reactions. " * 40
        answer_passage = (
            "On February 28, 2026, the first reported strike began according to the compiled timeline and witness accounts. "
            "The same report describes the opening wave as the beginning of the latest phase."
        )
        trailing_notes = "Additional commentary and aftermath analysis. " * 20
        fetcher.fetch.return_value = FetchDocument(
            requested_url="https://example.com/timeline",
            final_url="https://example.com/timeline",
            title="War timeline",
            excerpt="Timeline overview.",
            content_text=f"{leading_background}\n\n{answer_passage}\n\n{trailing_notes}",
            content_char_count=len(leading_background) + len(answer_passage) + len(trailing_notes) + 4,
            word_count=220,
            content_type="text/html",
            retrieval_method="direct_html",
            content_quality="usable",
            warnings=[],
        )

        bundle, context = await build_grounding_bundle(
            query="When did the first reported strike begin?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=1,
            fetch_limit=1,
            source_char_limit=320,
            total_context_chars=600,
            preview_chars=160,
        )

        self.assertEqual(bundle.summary.context_mode, "fetched_text")
        self.assertIn("February 28, 2026", context)
        self.assertIn("first reported strike began", bundle.fetched_sources[0].context_text)
        self.assertNotIn("Background context about regional tensions", bundle.fetched_sources[0].context_text)

    async def test_grounding_bundle_prefers_matching_entity_variants_over_generic_talk_mentions(self) -> None:
        search_provider = AsyncMock()
        search_provider.search.return_value = [
            SearchHit(
                title="Live analysis",
                url="https://example.com/live-analysis",
                snippet="Current shipping disruption and diplomacy update.",
                engine="mock",
            )
        ]

        fetcher = AsyncMock()
        strait_status = (
            "The Strait of Hormuz is not open to normal commercial traffic while the U.S. blockade remains in place, "
            "and several vessels have been seized."
        )
        off_topic_talks = (
            "A first round of peace talks between Lebanon and Israel took place at the State Department and focused on "
            "border monitoring and local ceasefire arrangements."
        )
        relevant_talks = (
            "Delegates from Iran and the United States could soon return to Pakistan for another round of peace talks, "
            "but Reuters and the Associated Press report that no date has been decided."
        )
        tail = "Additional live updates and background reporting. " * 18
        fetcher.fetch.return_value = FetchDocument(
            requested_url="https://example.com/live-analysis",
            final_url="https://example.com/live-analysis",
            title="Live analysis",
            excerpt="Current shipping disruption and diplomacy update.",
            content_text=f"{strait_status}\n\n{off_topic_talks}\n\n{relevant_talks}\n\n{tail}",
            content_char_count=len(strait_status) + len(off_topic_talks) + len(relevant_talks) + len(tail) + 6,
            word_count=220,
            content_type="text/html",
            retrieval_method="direct_html",
            content_quality="usable",
            warnings=[],
        )

        bundle, context = await build_grounding_bundle(
            query="Are the Straits of Hormuz open and what is the current state of the Iranian-American peace talks?",
            search_provider=search_provider,
            fetcher_client=fetcher,
            search_limit=1,
            fetch_limit=1,
            source_char_limit=520,
            total_context_chars=720,
            preview_chars=160,
        )

        self.assertEqual(bundle.summary.context_mode, "fetched_text")
        self.assertIn("Strait of Hormuz is not open", context)
        self.assertIn("Iran and the United States could soon return", context)
        self.assertNotIn("Lebanon and Israel", bundle.fetched_sources[0].context_text)

    def test_select_context_excerpt_respects_limit_for_status_queries(self) -> None:
        content_text = (
            "The Strait of Hormuz is not open to normal commercial traffic while the blockade remains in place. "
            "Officials say Iran and the United States remain at odds over the terms for restarting talks. "
        ) * 12

        excerpt = _select_context_excerpt(
            "Are the Straits of Hormuz open and are Iranian-American talks resuming?",
            content_text,
            220,
        )

        self.assertLessEqual(len(excerpt), 220)
        self.assertIn("Strait of Hormuz", excerpt)

    def test_grounded_request_discourages_prior_knowledge_language(self) -> None:
        grounded_request = build_grounded_model_request(
            query="What happened?",
            grounding_context="[S1] Example source text.",
            temperature=0.1,
            additional_system_prompt="Always cite sources.",
        )

        self.assertIn("Every substantive factual claim must cite", grounded_request.prompt)
        self.assertIn("sourced material is insufficient", grounded_request.prompt)
        self.assertIn("Do not mention your training data, knowledge cutoff, or prior knowledge", grounded_request.system_prompt)
        self.assertIn("Always cite sources.", grounded_request.system_prompt)

    def test_grounded_request_prefers_direct_answers_and_consecutive_citations(self) -> None:
        grounded_request = build_grounded_model_request(
            query="When did it happen?",
            grounding_context="[S1] Example source text.",
            temperature=0.1,
        )

        self.assertIn("Answer the question directly in the first sentence", grounded_request.prompt)
        self.assertIn("start with Yes, No, or Insufficient", grounded_request.prompt)
        self.assertIn("consecutive source IDs like [S1][S2]", grounded_request.prompt)
        self.assertIn("Never group multiple source IDs inside one bracket", grounded_request.prompt)
        self.assertIn("Use the smallest sufficient set of sources", grounded_request.prompt)

    def test_grounded_request_handles_snippet_context_mode(self) -> None:
        grounded_request = build_grounded_model_request(
            query="What happened?",
            grounding_context="[S1] Example snippet.",
            temperature=0.1,
            context_mode="search_snippets",
        )

        self.assertIn("supporting search-result snippets", grounded_request.prompt)
        self.assertIn("Search result snippets:", grounded_request.prompt)
        self.assertIn("article fetches were unavailable", grounded_request.system_prompt)

    def test_grounded_request_handles_hybrid_context_mode(self) -> None:
        grounded_request = build_grounded_model_request(
            query="What happened?",
            grounding_context="[S1] Example fetched text.\n\n[S2] Example snippet fallback.",
            temperature=0.1,
            context_mode="fetched_plus_snippets",
        )

        self.assertIn("Grounded sources and snippet fallbacks:", grounded_request.prompt)
        self.assertIn("Prefer fetched article text", grounded_request.prompt)
        self.assertIn("available only as labeled search-result snippets", grounded_request.system_prompt)

    def test_normalize_grounded_answer_rewrites_grouped_and_repeated_citations(self) -> None:
        normalized = normalize_grounded_answer(
            "The sources [S1], [S4], and [S4] mention ongoing talks.\nThey also cite [S5, S6]."
        )

        self.assertEqual(
            normalized,
            "The sources [S1][S4] mention ongoing talks. They also cite [S5][S6].",
        )


class SearchProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_searxng_auto_categories_separate_ordinary_and_current_queries(self) -> None:
        provider = SearxngSearchProvider(
            base_url="http://search-provider:8080",
            timeout_seconds=20.0,
            categories="auto",
        )
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://search-provider:8080/search"),
            content=json.dumps({"results": []}).encode("utf-8"),
        )
        client = MockAsyncClient(response=response)
        with patch("app.providers.httpx.AsyncClient", return_value=client):
            await provider.search("what is local inference", 5)
            self.assertEqual(client.last_get_params["categories"], "general")

            await provider.search("what is the current status of the ceasefire", 5)
            self.assertEqual(client.last_get_params["categories"], "general,news")

    async def test_searxng_auto_categories_do_not_treat_open_source_as_current_news(self) -> None:
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://search-provider:8080/search"),
            json={"results": []},
        )
        client = MockAsyncClient(response=response)
        provider = SearxngSearchProvider(
            base_url="http://search-provider:8080",
            categories="auto",
            language="",
            time_range="",
            engines="",
            timeout_seconds=20,
        )

        with patch("app.providers.httpx.AsyncClient", return_value=client):
            await provider.search("What is open source software?", 8)

        self.assertEqual(client.last_get_params["categories"], "general")

    async def test_searxng_auto_engines_keep_news_out_of_ordinary_queries(self) -> None:
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://search-provider:8080/search"),
            json={"results": []},
        )
        client = MockAsyncClient(response=response)
        provider = SearxngSearchProvider(
            base_url="http://search-provider:8080",
            categories="auto",
            language="",
            time_range="",
            engines="brave,wikipedia,duckduckgo news,google news,reuters",
            timeout_seconds=20,
        )

        with patch("app.providers.httpx.AsyncClient", return_value=client):
            await provider.search("What is local inference?", 8)
            self.assertEqual(client.last_get_params["engines"], "brave,wikipedia")

            await provider.search("What is the current state of the ceasefire?", 8)
            self.assertEqual(
                client.last_get_params["engines"],
                "brave,wikipedia,duckduckgo news,google news,reuters",
            )

    async def test_searxng_reports_unresponsive_engines_when_no_results_are_usable(self) -> None:
        provider = SearxngSearchProvider(
            base_url="http://search-provider:8080",
            timeout_seconds=20.0,
        )
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://search-provider:8080/search"),
            content=json.dumps(
                {
                    "results": [{"title": "missing url"}, {"url": ""}],
                    "unresponsive_engines": [["brave", "timeout"], ["startpage", "403"]],
                }
            ).encode("utf-8"),
        )
        with patch(
            "app.providers.httpx.AsyncClient",
            return_value=MockAsyncClient(response=response),
        ):
            with self.assertRaisesRegex(ProviderError, "unresponsive engines: brave, startpage"):
                await provider.search("privacy", 5)

    async def test_searxng_search_passes_tuned_query_parameters(self) -> None:
        provider = build_search_provider(
            Settings(
                SEARCH_PROVIDER="searxng",
                SEARCH_BASE_URL="http://search-provider:8080",
                SEARCH_CATEGORIES="general,news",
                SEARCH_LANGUAGE="all",
                SEARCH_TIME_RANGE="month",
                SEARCH_ENGINES="duckduckgo,wikipedia",
            )
        )
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://search-provider:8080/search"),
            content=json.dumps(
                {
                    "results": [
                        {
                            "title": "Alpha",
                            "url": "https://example.com/article",
                            "content": "Alpha snippet",
                            "engine": "duckduckgo",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        client = MockAsyncClient(response=response)
        with patch("app.providers.httpx.AsyncClient", return_value=client):
            results = await provider.search("privacy", 5)

        self.assertEqual(len(results), 1)
        self.assertEqual(client.last_get_params["categories"], "general,news")
        self.assertEqual(client.last_get_params["language"], "all")
        self.assertEqual(client.last_get_params["time_range"], "month")
        self.assertEqual(client.last_get_params["engines"], "duckduckgo,wikipedia")
        self.assertEqual(client.last_get_params["format"], "json")
        self.assertEqual(client.last_get_params["pageno"], 1)

    async def test_yacy_search_normalizes_channel_items(self) -> None:
        provider = YacySearchProvider(
            base_url="http://yacy-search:8090",
            timeout_seconds=20.0,
        )
        response = httpx.Response(
            200,
            request=httpx.Request("GET", "http://yacy-search:8090/yacysearch.json"),
            content=json.dumps(
                {
                    "channels": [
                        {
                            "items": [
                                {
                                    "title": "Alpha",
                                    "link": "https://example.com/article",
                                    "description": "Alpha snippet",
                                },
                                {
                                    "link": "https://example.org/post",
                                    "content": "Beta snippet",
                                },
                            ]
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        with patch("app.providers.httpx.AsyncClient", return_value=MockAsyncClient(response=response)):
            results = await provider.search("privacy", 2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Alpha")
        self.assertEqual(results[0].snippet, "Alpha snippet")
        self.assertEqual(results[1].title, "https://example.org/post")
        self.assertEqual(results[1].engine, "yacy")


if __name__ == "__main__":
    unittest.main()
