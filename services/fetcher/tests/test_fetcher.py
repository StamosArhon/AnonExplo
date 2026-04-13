import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import FetcherError, app, extract_document, validate_requested_url


class FetcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_extract_document_collects_readable_text(self) -> None:
        html = """
        <html>
          <head><title>Example Article</title></head>
          <body>
            <article>
              <h1>Headline</h1>
              <p>First paragraph.</p>
              <p>Second paragraph.</p>
            </article>
          </body>
        </html>
        """
        document = extract_document(html, "https://example.com/article", 1000)
        self.assertEqual(document["title"], "Example Article")
        self.assertIn("First paragraph.", document["content_text"])
        self.assertIn("Second paragraph.", document["content_text"])
        self.assertGreater(document["content_char_count"], 0)
        self.assertGreater(document["word_count"], 0)

    def test_validate_requested_url_blocks_localhost(self) -> None:
        with self.assertRaises(FetcherError):
            validate_requested_url("http://localhost:8000/private")

    def test_validate_requested_url_accepts_public_https(self) -> None:
        validate_requested_url("https://example.com/article")

    @patch("app.main.fetch_html", new_callable=AsyncMock)
    @patch("app.main.validate_requested_url")
    def test_fetch_endpoint_allows_integer_count_fields(
        self,
        validate_requested_url_mock,
        fetch_html_mock: AsyncMock,
    ) -> None:
        fetch_html_mock.return_value = {
            "requested_url": "https://example.com/article",
            "final_url": "https://example.com/article",
            "title": "Example",
            "excerpt": "Example excerpt",
            "content_text": "Example body",
            "content_char_count": 12,
            "word_count": 2,
            "content_type": "text/html",
        }

        response = self.client.post("/api/v1/fetch", json={"url": "https://example.com/article"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["content_char_count"], 12)
        self.assertEqual(payload["word_count"], 2)
        validate_requested_url_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
