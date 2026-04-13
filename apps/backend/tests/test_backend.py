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
from app.grounding import build_grounded_model_request, build_grounding_bundle
from app.main import app, build_model_provider, build_search_provider
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
        self.assertEqual(payload["search"]["categories"], "general,news")
        self.assertEqual(payload["search"]["language"], "all")
        self.assertEqual(payload["search"]["time_range"], "none")

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

        self.assertEqual([item.source_id for item in bundle.selected_sources], ["S3", "S2", "S4"])
        self.assertEqual([item.source_id for item in bundle.fetched_sources], ["S3", "S4"])
        self.assertEqual(bundle.summary.selected_sources, 3)
        self.assertEqual(bundle.summary.fetched_sources, 2)
        self.assertEqual(bundle.summary.failed_sources, 1)
        self.assertEqual(bundle.summary.context_mode, "fetched_text")
        self.assertEqual(bundle.search_results[0].status, "unselected")
        self.assertEqual(bundle.search_results[1].status, "selected")
        self.assertIn("[S3]", context)
        self.assertIn("[S4]", context)

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
        self.assertEqual(bundle.summary.context_mode, "fetched_text")
        self.assertEqual(bundle.errors[0].code, "content_too_thin")
        self.assertFalse(bundle.errors[0].retryable)
        self.assertEqual(bundle.fetched_sources[0].source_id, "S2")
        self.assertEqual(bundle.fetched_sources[0].retrieval_method, "direct_html")
        self.assertEqual(bundle.fetched_sources[0].content_quality, "usable")
        self.assertIn("[S2]", context)

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


class SearchProviderTests(unittest.IsolatedAsyncioTestCase):
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
