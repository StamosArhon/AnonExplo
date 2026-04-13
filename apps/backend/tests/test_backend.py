import os
import unittest
from collections import deque
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

os.environ["MODEL_PROVIDER"] = "openai_compatible"
os.environ["MODEL_BASE_URL"] = "http://model-backend:8080/v1"
os.environ["MODEL_NAME"] = "test-model"
os.environ["SEARCH_PROVIDER"] = "searxng"
os.environ["SEARCH_BASE_URL"] = "http://search-provider:8080"
os.environ["FETCH_BASE_URL"] = "http://fetcher:8081"

from app.main import app
from app.providers import FetchDocument, ProviderError, SearchHit


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint_exposes_provider_summary(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["providers"]["model"], "openai_compatible")
        self.assertEqual(payload["providers"]["model_runtime_profile"], "llama.cpp-cuda")

    def test_provider_endpoint_returns_configured_base_urls(self) -> None:
        response = self.client.get("/api/v1/system/providers")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"]["model_name"], "test-model")
        self.assertTrue(payload["search"]["base_url"].startswith("http://search-provider"))

    @patch("app.main.build_model_provider")
    def test_chat_endpoint_returns_provider_response(self, build_model_provider: AsyncMock) -> None:
        provider = AsyncMock()
        provider.chat.return_value = {
            "model": "test-model",
            "answer": "hello from the model",
            "usage": {"total_tokens": 12},
        }
        build_model_provider.return_value = provider

        response = self.client.post("/api/v1/model/chat", json={"prompt": "hello"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "hello from the model")

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

        model_provider = AsyncMock()
        model_provider.chat.return_value = {
            "model": "test-model",
            "answer": "Grounded answer [S1]",
            "usage": {"total_tokens": 42},
        }
        build_model_provider.return_value = model_provider

        response = self.client.post("/api/v1/grounding/answer", json={"query": "What does Alpha say?"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer_status"], "grounded")
        self.assertEqual(payload["answer"], "Grounded answer [S1]")
        prompt = model_provider.chat.await_args.kwargs["prompt"]
        self.assertIn("[S1]", prompt)
        self.assertIn("Alpha content for the grounding path.", prompt)


if __name__ == "__main__":
    unittest.main()
