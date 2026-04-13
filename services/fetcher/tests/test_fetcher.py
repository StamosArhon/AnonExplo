import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import (
    FetcherError,
    Settings,
    app,
    extract_document,
    extract_wikimedia_page_title,
    fetch_document,
    fetch_html,
    fetch_wikimedia_api_document,
    should_use_wikimedia_api,
    validate_requested_url,
)


class MockStreamResponse:
    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}
        self._body = body

    async def aread(self) -> bytes:
        return self._body

    async def aiter_bytes(self):
        yield self._body


class MockStreamContext:
    def __init__(self, response: MockStreamResponse) -> None:
        self.response = response

    async def __aenter__(self) -> MockStreamResponse:
        return self.response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class MockStreamingClient:
    def __init__(self, response: MockStreamResponse) -> None:
        self.response = response

    async def __aenter__(self) -> "MockStreamingClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def stream(self, method: str, url: str) -> MockStreamContext:
        return MockStreamContext(self.response)


class MockJsonResponse:
    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        headers: dict[str, str] | None = None,
        payload: dict | None = None,
        body: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}
        self._payload = payload or {}
        self._body = body

    async def aread(self) -> bytes:
        if self._body:
            return self._body
        return str(self._payload).encode("utf-8")

    def json(self) -> dict:
        return self._payload


class MockJsonClient:
    def __init__(self, response: MockJsonResponse) -> None:
        self.response = response

    async def __aenter__(self) -> "MockJsonClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def get(self, url: str, params: dict | None = None) -> MockJsonResponse:
        return self.response


class FetcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_extract_document_collects_readable_text(self) -> None:
        settings = Settings(FETCH_MAX_TEXT_CHARS=1000)
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
        document = extract_document(html, "https://example.com/article", settings)
        self.assertEqual(document["title"], "Example Article")
        self.assertIn("First paragraph.", document["content_text"])
        self.assertIn("Second paragraph.", document["content_text"])
        self.assertGreater(document["content_char_count"], 0)
        self.assertGreater(document["word_count"], 0)
        self.assertEqual(document["content_quality"], "thin")
        self.assertTrue(document["warnings"])

    def test_extract_document_marks_usable_content_when_thresholds_are_met(self) -> None:
        settings = Settings(
            FETCH_MAX_TEXT_CHARS=5000,
            FETCH_MIN_CONTENT_CHARS=60,
            FETCH_MIN_WORD_COUNT=10,
        )
        html = """
        <html>
          <head><title>Example Article</title></head>
          <body>
            <article>
              <h1>Headline</h1>
              <p>First paragraph with enough readable words to count for a usable extraction.</p>
              <p>Second paragraph adds more detail and keeps the content above the threshold.</p>
            </article>
          </body>
        </html>
        """
        document = extract_document(html, "https://example.com/article", settings)
        self.assertEqual(document["content_quality"], "usable")
        self.assertEqual(document["warnings"], [])

    def test_validate_requested_url_blocks_localhost(self) -> None:
        with self.assertRaises(FetcherError):
            validate_requested_url("http://localhost:8000/private")

    def test_validate_requested_url_accepts_public_https(self) -> None:
        validate_requested_url("https://example.com/article")

    def test_extract_wikimedia_page_title_from_article_path(self) -> None:
        self.assertEqual(
            extract_wikimedia_page_title("https://en.wikipedia.org/wiki/Twelve-Day_War"),
            "Twelve-Day War",
        )

    def test_extract_wikimedia_page_title_from_index_query(self) -> None:
        self.assertEqual(
            extract_wikimedia_page_title("https://www.mediawiki.org/w/index.php?title=API:Etiquette"),
            "API:Etiquette",
        )

    def test_extract_wikimedia_page_title_rejects_special_pages(self) -> None:
        self.assertIsNone(
            extract_wikimedia_page_title("https://en.wikipedia.org/wiki/Special:Random"),
        )

    def test_should_use_wikimedia_api_requires_opt_in_and_supported_url(self) -> None:
        disabled_settings = Settings(FETCH_WIKIMEDIA_API_ENABLED=False)
        enabled_settings = Settings(FETCH_WIKIMEDIA_API_ENABLED=True)

        self.assertFalse(
            should_use_wikimedia_api("https://en.wikipedia.org/wiki/Twelve-Day_War", disabled_settings),
        )
        self.assertTrue(
            should_use_wikimedia_api("https://en.wikipedia.org/wiki/Twelve-Day_War", enabled_settings),
        )
        self.assertFalse(
            should_use_wikimedia_api("https://example.com/article", enabled_settings),
        )

    @patch("app.main.fetch_document", new_callable=AsyncMock)
    @patch("app.main.validate_requested_url")
    def test_fetch_endpoint_allows_integer_count_fields(
        self,
        validate_requested_url_mock,
        fetch_document_mock: AsyncMock,
    ) -> None:
        fetch_document_mock.return_value = {
            "requested_url": "https://example.com/article",
            "final_url": "https://example.com/article",
            "title": "Example",
            "excerpt": "Example excerpt",
            "content_text": "Example body",
            "content_char_count": 12,
            "word_count": 2,
            "content_type": "text/html",
            "retrieval_method": "direct_html",
            "content_quality": "usable",
            "warnings": [],
        }

        response = self.client.post("/api/v1/fetch", json={"url": "https://example.com/article"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["content_char_count"], 12)
        self.assertEqual(payload["word_count"], 2)
        self.assertEqual(payload["retrieval_method"], "direct_html")
        self.assertEqual(payload["content_quality"], "usable")
        validate_requested_url_mock.assert_called_once()

    @patch("app.main.fetch_document", new_callable=AsyncMock)
    @patch("app.main.validate_requested_url")
    def test_fetch_endpoint_returns_structured_fetcher_errors(
        self,
        validate_requested_url_mock,
        fetch_document_mock: AsyncMock,
    ) -> None:
        fetch_document_mock.side_effect = FetcherError(
            "Remote site denied automated fetching under its robot policy.",
            code="blocked_by_remote_policy",
            status_code=502,
            upstream_status=403,
            retryable=False,
        )

        response = self.client.post("/api/v1/fetch", json={"url": "https://example.com/article"})

        self.assertEqual(response.status_code, 502)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "blocked_by_remote_policy")
        self.assertEqual(payload["detail"]["upstream_status"], 403)
        self.assertFalse(payload["detail"]["retryable"])
        validate_requested_url_mock.assert_called_once()


class FetcherHttpBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_document_prefers_wikimedia_api_when_enabled(self) -> None:
        settings = Settings(
            FETCH_WIKIMEDIA_API_ENABLED=True,
            FETCH_WIKIMEDIA_API_USER_AGENT="AnonExploFetcher/0.1 (mailto:test@example.com)",
        )

        with (
            patch("app.main.fetch_wikimedia_api_document", new_callable=AsyncMock) as wikimedia_mock,
            patch("app.main.fetch_html", new_callable=AsyncMock) as fetch_html_mock,
        ):
            wikimedia_mock.return_value = {
                "requested_url": "https://en.wikipedia.org/wiki/Twelve-Day_War",
                "final_url": "https://en.wikipedia.org/wiki/Twelve-Day_War",
                "title": "Twelve-Day War",
                "excerpt": "Excerpt",
                "content_text": "Body",
                "content_char_count": 4,
                "word_count": 1,
                "content_type": "application/json",
                "retrieval_method": "wikimedia_parse_api",
                "content_quality": "thin",
                "warnings": [],
            }

            document = await fetch_document("https://en.wikipedia.org/wiki/Twelve-Day_War", settings)

        self.assertEqual(document["retrieval_method"], "wikimedia_parse_api")
        wikimedia_mock.assert_awaited_once()
        fetch_html_mock.assert_not_called()

    async def test_fetch_html_classifies_robot_policy_blocks(self) -> None:
        response = MockStreamResponse(
            status_code=403,
            url="https://example.com/article",
            headers={"content-type": "text/html"},
            body=b"<html><body>Access denied by robot policy.</body></html>",
        )

        with patch("app.main.httpx.AsyncClient", return_value=MockStreamingClient(response)):
            with self.assertRaises(FetcherError) as context:
                await fetch_html("https://example.com/article", Settings())

        self.assertEqual(context.exception.code, "blocked_by_remote_policy")
        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(context.exception.upstream_status, 403)
        self.assertFalse(context.exception.retryable)

    async def test_fetch_wikimedia_api_document_returns_structured_article_content(self) -> None:
        settings = Settings(
            FETCH_WIKIMEDIA_API_ENABLED=True,
            FETCH_WIKIMEDIA_API_USER_AGENT="AnonExploFetcher/0.1 (mailto:test@example.com)",
            FETCH_MIN_CONTENT_CHARS=20,
            FETCH_MIN_WORD_COUNT=4,
        )
        response = MockJsonResponse(
            status_code=200,
            url="https://en.wikipedia.org/w/api.php",
            headers={"content-type": "application/json; charset=utf-8"},
            payload={
                "parse": {
                    "title": "Twelve-Day War",
                    "displaytitle": "<i>Twelve-Day War</i>",
                    "text": """
                        <div class="mw-parser-output">
                          <p>The Twelve-Day War began in February 2026.</p>
                          <p>United States and Israeli forces launched the opening strikes.</p>
                        </div>
                    """,
                }
            },
        )

        with patch("app.main.httpx.AsyncClient", return_value=MockJsonClient(response)):
            document = await fetch_wikimedia_api_document(
                "https://en.wikipedia.org/wiki/Twelve-Day_War",
                settings,
            )

        self.assertEqual(document["retrieval_method"], "wikimedia_parse_api")
        self.assertEqual(document["title"], "Twelve-Day War")
        self.assertEqual(document["final_url"], "https://en.wikipedia.org/wiki/Twelve-Day_War")
        self.assertEqual(document["content_type"], "application/json; charset=utf-8")
        self.assertEqual(document["content_quality"], "usable")
        self.assertIn("The Twelve-Day War began in February 2026.", document["content_text"])

    async def test_fetch_wikimedia_api_document_requires_contactable_user_agent(self) -> None:
        settings = Settings(
            FETCH_WIKIMEDIA_API_ENABLED=True,
            FETCH_WIKIMEDIA_API_USER_AGENT="",
        )

        with self.assertRaises(FetcherError) as context:
            await fetch_wikimedia_api_document(
                "https://en.wikipedia.org/wiki/Twelve-Day_War",
                settings,
            )

        self.assertEqual(context.exception.code, "wikimedia_api_user_agent_required")


if __name__ == "__main__":
    unittest.main()
