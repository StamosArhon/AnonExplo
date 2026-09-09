"""Synthetic browser-route benchmark. No browser data, result dumps or history.

Use test-browser-search.ps1 for live runs: it checks VPN isolation first.
By default only aggregate metrics leave memory. Explicit --review-top5 displays
bounded public-fixture snippets for manual grading; do not capture transcripts.
A host match is a navigation proxy, not a judgement of general relevance.
"""
import argparse
import datetime
import html
import json
import re
import sys
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

# Public, fixed examples, never derived from browser history. Extra fields are
# category, time range, and a predeclared manual top-five relevance rubric.
# Informational/news questions deliberately have no preferred host.
INFORMATIONAL = (
    ("info-sky", "why is the sky blue Rayleigh scattering", "en", None, None, None,
     "Explains shorter-wavelength scattering in Earth's atmosphere; not just sky photos."),
    ("info-generators", "Python generators versus lists memory lazy evaluation", "en", None, None, None,
     "Explains lazy iteration and memory tradeoffs, not merely Python installation."),
    ("info-solar", "how photovoltaic solar cells convert sunlight into electricity", "en", None, None, None,
     "Explains photovoltaic conversion; distinguish explanatory material from sales pages."),
    ("info-water-el", "πώς λειτουργεί ο κύκλος του νερού εξάτμιση συμπύκνωση", "el", None, None, None,
     "Explains evaporation, condensation and precipitation in readable Greek."),
    ("info-dns-el", "τι είναι το DNS και πώς λειτουργεί", "el", None, None, None,
     "Explains domain-name resolution in Greek, not only a DNS service advert."),
    ("info-compost-el", "πώς γίνεται η οικιακή κομποστοποίηση τι υλικά βάζουμε", "el", None, None, None,
     "Practical Greek guidance on home composting and suitable materials, not just product listings."),
)
NEWS_MONTH = (
    ("news-space", "space exploration", "en", None, "news", "month",
     "Recent reporting about space exploration, not evergreen explainers or unrelated space uses."),
    ("news-energy-el", "ανανεώσιμες πηγές ενέργειας", "el", None, "news", "month",
     "Recent Greek-language reporting about renewable energy, not evergreen sales pages."),
    ("news-technology", "semiconductor research", "en", None, "news", "month",
     "Recent reporting on semiconductor research, not generic investment pages."),
    ("news-science-el", "επιστημονική έρευνα", "el", None, "news", "month",
     "Recent Greek-language science/research reporting, not courses or institutional homepages."),
)
NEWS = tuple((*f[:5], None, f[6]) for f in NEWS_MONTH)
SUITES = {"navigation": FIXTURES, "informational": INFORMATIONAL,
          "news": NEWS, "news-month": NEWS_MONTH}
ENGINE_NAMES = frozenset(("brave", "brave.news", "bing", "duckduckgo", "google", "startpage",
                          "mojeek", "qwant", "yahoo", "wikipedia", "duckduckgo news",
                          "google news", "reuters", "arxiv", "pubmed", "crossref"))


def safe_engine(name):
    return name if isinstance(name, str) and name in ENGINE_NAMES else "unknown"


def error_metrics(failures):
    # Exact classifications only: upstream error text can contain query URLs.
    codes = {"too many requests": "rate_limited", "captcha": "captcha",
             "access denied": "access_denied", "timeout": "timeout"}
    return [{"engine": safe_engine(f[0]),
             "kind": codes.get(f[1].lower(), "other") if isinstance(f[1], str) else "other"}
            if isinstance(f, (list, tuple)) and len(f) >= 2 else {"engine": "unknown", "kind": "other"}
            for f in failures]


def review_text(value, limit):
    if not isinstance(value, str):
        return ""
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    # JSON escaping plus control-character removal: untrusted result text is
    # evidence to grade, never instructions or terminal escape sequences.
    return " ".join("".join(c for c in value if c.isprintable() or c.isspace()).split())[:limit]


def top5_review(payload):
    return [{"rank": i, "engines": sorted({safe_engine(e) for e in r.get("engines", [])}),
             "published_age_days": publication_age_days(r),
             "title": review_text(r.get("title"), 180),
             "snippet": review_text(r.get("content"), 400)}
            if isinstance(r, dict) else {"rank": i, "title": "", "snippet": ""}
            for i, r in enumerate(payload.get("results", [])[:5], 1)]


def publication_age_days(result, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    try:
        value = result.get("publishedDate")
        date = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)
        return (now - date).total_seconds() / 86400
    except (AttributeError, TypeError, ValueError):
        return None


def freshness_metrics(results, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    dated = recent = future = 0
    for result in results[:5]:
        age = publication_age_days(result, now)
        if age is None:
            continue
        dated += 1
        recent += 0 <= age <= 31
        future += age < 0
    return {"top5_dated": dated, "top5_within_31_days": recent, "top5_future_dates": future}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not follow even a local redirect: this benchmark measures /search.
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def make_request(port, fixture, language_mode, engine=None):
    sample_id, query, language, _ = fixture[:4]
    params = {"q": query, "format": "json"}
    if language_mode == "explicit":
        params["language"] = language
    # SearXNG unions category and engine selectors: NEVER send both.
    if not engine and len(fixture) > 4 and fixture[4]:
        params["categories"] = fixture[4]
    if len(fixture) > 5 and fixture[5]:
        params["time_range"] = fixture[5]
    if engine:
        if engine not in ENGINE_NAMES:
            raise ValueError("Engine outside reviewed catalogue")
        params["engines"] = engine
    # No cookies or engine overrides by default. News explicitly selects its
    # native tab; a single-engine diagnostic omits the category selector.
    return urllib.request.Request(
        f"http://127.0.0.1:{port}/search?{urllib.parse.urlencode(params)}",
        headers={"Accept-Language": "en-US,en;q=0.9", "User-Agent": "AnonExplo-Synthetic-Benchmark/1"},
    )


def metrics(payload, expected_host):
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Invalid result list")
    hosts = []
    contributors = {}
    for result in results:
        try:
            url = urllib.parse.urlsplit(result.get("url", ""))
            host = (url.hostname or "").lower().rstrip(".") if url.scheme in ("http", "https") else ""
        except (ValueError, AttributeError, TypeError):
            host = ""
        hosts.append(host)
        if isinstance(result, dict):
            for engine in set(result.get("engines", [])):
                name = safe_engine(engine)
                contributors[name] = contributors.get(name, 0) + 1
    rank = next((i for i, host in enumerate(hosts, 1)
                 if expected_host and (host == expected_host or host.endswith("." + expected_host))), None)
    # Never echo raw upstream exception messages: they can contain queries/URLs.
    failures = payload.get("unresponsive_engines", [])
    return {
        "results": len(results), "domains": len(set(hosts) - {""}),
        "expected_top5": rank is not None and rank <= 5,
        "expected_rank": rank, "reciprocal_rank": round(1 / rank, 3) if rank else 0,
        "top5_domains": len(set(hosts[:5]) - {""}),
        "contributing_engines": len(contributors), "engine_errors": len(failures),
        "engine_result_counts": contributors, "failures": error_metrics(failures),
    }


def run(port, language_mode, samples, pause=15, suite="navigation", engine=None, review=False):
    # Ignore host HTTP_PROXY settings: only the exact loopback endpoint is used.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    fixtures = SUITES[suite]
    if not 1 <= samples <= len(fixtures):
        raise ValueError("Samples exceeds suite size")
    if engine or suite != "navigation":
        # Local catalogue check is not a search; never silently accept an
        # ignored selector which could send the query to default engines.
        try:
            with opener.open(f"http://127.0.0.1:{port}/config", timeout=10) as response:
                config = json.loads(response.read(1_000_001))
            categories = {f[4] if len(f) > 4 and f[4] else "general" for f in fixtures[:samples]}
            candidates = [e for e in config["engines"]
                          if categories <= set(e.get("categories", []))
                          and (e.get("name") == engine if engine else e.get("enabled"))]
            if engine and engine not in ENGINE_NAMES:
                raise ValueError("Unreviewed engine")
            if not candidates:
                raise ValueError("Engine/category unavailable")
            filtered = any(len(f) > 5 and f[5] for f in fixtures[:samples])
            skipped = [safe_engine(e.get("name")) for e in candidates
                       if filtered and not e.get("time_range_support")]
            eligible = [safe_engine(e.get("name")) for e in candidates
                        if not filtered or e.get("time_range_support")]
            print(json.dumps({"selection": engine or "instance_defaults", "eligible_engines": eligible,
                              "skipped_unsupported_time_filter": skipped}), flush=True)
            if not eligible:
                raise ValueError("No eligible engines")
        except Exception:
            print(json.dumps({"status": "invalid_engine_selection", "stopped": True}))
            return 2
    rows = []
    for fixture in fixtures[:samples]:
        started = time.monotonic()
        try:
            with opener.open(make_request(port, fixture, language_mode, engine), timeout=25) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise ValueError("Response too large")
                payload = json.loads(raw)
            row = {"sample": fixture[0], "mode": language_mode,
                   **metrics(payload, fixture[3]), "seconds": round(time.monotonic() - started, 2)}
            if engine and set(row["engine_result_counts"]) - {engine}:
                raise ValueError("Engine isolation failed")
            if fixture[3] is None:
                for key in ("expected_top5", "expected_rank", "reciprocal_rank"):
                    row.pop(key)
            if suite.startswith("news"):
                row.update(freshness_metrics(payload.get("results", [])))
        except Exception:
            print(json.dumps({"sample": fixture[0], "status": "request_failed", "stopped": True}))
            return 2
        print(json.dumps(row), flush=True)
        if review:
            print(json.dumps({"sample": fixture[0], "untrusted_review_only": top5_review(payload),
                              "rubric": fixture[6] if len(fixture) > 6 else "Useful destination for this navigation query."}, ensure_ascii=False), flush=True)
        rows.append(row)
        if row["engine_errors"] or not row["results"]:
            # Stop the whole suite; do not repeatedly hit a degraded engine,
            # clear suspensions, rotate exits, or try direct upstream access.
            print(json.dumps({"status": "degraded", "stopped": True}))
            return 2
        if len(rows) < samples:
            time.sleep(pause)
    summary = {"samples": len(rows), "suite": suite, "mode": language_mode,
               "selection": engine or "instance_defaults",
               "mean_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 2)}
    if suite == "navigation":
        summary.update(top5_matches=sum(r["expected_top5"] for r in rows),
                       mean_reciprocal_rank=round(sum(r["reciprocal_rank"] for r in rows) / len(rows), 3))
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, choices=range(1024, 65536), default=8085, metavar="PORT")
    parser.add_argument("--language-mode", choices=("browser", "explicit"), default="browser")
    parser.add_argument("--suite", choices=tuple(SUITES), default="navigation")
    parser.add_argument("--engine", choices=sorted(ENGINE_NAMES))
    parser.add_argument("--review-top5", action="store_true", help="Explicitly display bounded public-fixture titles/snippets for manual review; no files written.")
    parser.add_argument("--pause", type=int, choices=range(10, 61), default=15, metavar="SECONDS")
    parser.add_argument("--samples", type=int, choices=range(1, 7))
    args = parser.parse_args()
    samples = args.samples if args.samples is not None else len(SUITES[args.suite])
    if samples > len(SUITES[args.suite]):
        parser.error("--samples exceeds selected suite size")
    raise SystemExit(run(args.port, args.language_mode, samples, pause=args.pause, suite=args.suite,
                         engine=args.engine, review=args.review_top5))
