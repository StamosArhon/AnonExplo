"""Synthetic browser-route benchmark. No browser data, result dumps or history.

Use test-browser-search.ps1 for live runs: it checks VPN isolation first.
Only aggregate metrics leave memory. A host match is a navigation proxy,
not a judgement that a result is correct or generally relevant.
"""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request


FIXTURES = (
    ("navigation-design", "Behance", "en", "behance.net"),
    ("navigation-python", "Python programming language", "en", "python.org"),
    ("technical-docker", "Docker Compose networking service network_mode", "en", "docs.docker.com"),
    ("greek-museum", "Εθνικό Αρχαιολογικό Μουσείο", "el", "namuseum.gr"),
    ("greek-acropolis", "Μουσείο Ακρόπολης", "el", "theacropolismuseum.gr"),
    ("greek-services", "gov.gr έκδοση υπεύθυνης δήλωσης", "el", "gov.gr"),
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not follow even a local redirect: this benchmark measures /search.
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def make_request(port, fixture, language_mode):
    sample_id, query, language, _ = fixture
    params = {"q": query, "format": "json"}
    if language_mode == "explicit":
        params["language"] = language
    # No engines/categories/cookies: evaluate instance defaults like a fresh
    # address-bar request, not the legacy backend's overrides.
    return urllib.request.Request(
        f"http://127.0.0.1:{port}/search?{urllib.parse.urlencode(params)}",
        headers={"Accept-Language": "en-US,en;q=0.9", "User-Agent": "AnonExplo-Synthetic-Benchmark/1"},
    )


def metrics(payload, expected_host):
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Invalid result list")
    hosts = []
    contributors = set()
    for result in results:
        try:
            url = urllib.parse.urlsplit(result.get("url", ""))
            host = (url.hostname or "").lower().rstrip(".") if url.scheme in ("http", "https") else ""
        except (ValueError, AttributeError, TypeError):
            host = ""
        hosts.append(host)
        if isinstance(result, dict):
            contributors.update(e for e in result.get("engines", []) if isinstance(e, str))
    rank = next((i for i, host in enumerate(hosts, 1)
                 if host == expected_host or host.endswith("." + expected_host)), None)
    # Never echo raw upstream exception messages: they can contain queries/URLs.
    failures = payload.get("unresponsive_engines", [])
    return {
        "results": len(results), "domains": len(set(hosts) - {""}),
        "expected_top5": rank is not None and rank <= 5,
        "expected_rank": rank, "reciprocal_rank": round(1 / rank, 3) if rank else 0,
        "top5_domains": len(set(hosts[:5]) - {""}),
        "contributing_engines": len(contributors), "engine_errors": len(failures),
    }


def run(port, language_mode, samples, pause=5):
    # Ignore host HTTP_PROXY settings: only the exact loopback endpoint is used.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    rows = []
    for fixture in FIXTURES[:samples]:
        started = time.monotonic()
        try:
            with opener.open(make_request(port, fixture, language_mode), timeout=25) as response:
                payload = json.loads(response.read(4_000_001))
            row = {"sample": fixture[0], "mode": language_mode,
                   **metrics(payload, fixture[3]), "seconds": round(time.monotonic() - started, 2)}
        except Exception:
            print(json.dumps({"sample": fixture[0], "status": "request_failed", "stopped": True}))
            return 2
        print(json.dumps(row), flush=True)
        rows.append(row)
        if row["engine_errors"] or not row["results"]:
            # Stop the whole suite; do not repeatedly hit a degraded engine,
            # clear suspensions, rotate exits, or try direct upstream access.
            print(json.dumps({"status": "degraded", "stopped": True}))
            return 2
        if len(rows) < samples:
            time.sleep(pause)
    print(json.dumps({"samples": len(rows), "mode": language_mode,
                      "top5_matches": sum(r["expected_top5"] for r in rows),
                      "mean_reciprocal_rank": round(sum(r["reciprocal_rank"] for r in rows) / len(rows), 3),
                      "mean_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 2)}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, choices=range(1024, 65536), default=8085, metavar="PORT")
    parser.add_argument("--language-mode", choices=("browser", "explicit"), default="browser")
    parser.add_argument("--samples", type=int, choices=range(1, len(FIXTURES) + 1), default=len(FIXTURES))
    args = parser.parse_args()
    raise SystemExit(run(args.port, args.language_mode, args.samples))
