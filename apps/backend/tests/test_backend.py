import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

os.environ["MODEL_PROVIDER"] = "openai_compatible"
os.environ["MODEL_BASE_URL"] = "http://model-backend:8080/v1"
os.environ["MODEL_NAME"] = "test-model"
os.environ["SEARCH_PROVIDER"] = "searxng"
os.environ["SEARCH_BASE_URL"] = "http://search-provider:8080"
os.environ["FETCH_BASE_URL"] = "http://fetcher:8081"

from app.main import app


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint_exposes_provider_summary(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["providers"]["model"], "openai_compatible")

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


if __name__ == "__main__":
    unittest.main()
