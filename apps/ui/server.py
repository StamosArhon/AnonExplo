import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


STATIC_DIR = Path(__file__).parent / "static"


class UIRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/config.json":
            payload = {
                "apiBaseUrl": os.environ.get("UI_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
                "environment": os.environ.get("UI_ENVIRONMENT", "local"),
                "standaloneSearchUrl": os.environ.get(
                    "UI_STANDALONE_SEARCH_URL",
                    "http://127.0.0.1:8085",
                ),
            }
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/":
            self.path = "/index.html"

        return super().do_GET()


if __name__ == "__main__":
    host = os.environ.get("UI_HOST", "0.0.0.0")
    port = int(os.environ.get("UI_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), UIRequestHandler)
    server.serve_forever()
