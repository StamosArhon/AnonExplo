import unittest

from app.main import FetcherError, extract_document, validate_requested_url


class FetcherTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
