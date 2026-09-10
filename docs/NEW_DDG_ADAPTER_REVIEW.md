# New DDG Adapter Applicability Review (2026-09-10)

Follow-up to the user's request to proceed: check for genuinely new upstream
evidence, review applicability/request safety offline, validate and close out.
Branch stamos/new-ddg-adapter-review from main 3200f4c. No implementation,
production update, engine enablement, challenge execution or provider query.

## New Evidence

Official release metadata still reports curl_cffi v0.16.3 and curl-impersonate
v2.2.2, already compared. SearXNG advanced from ba055b3 to 42e1d61 with two changes:

- [DuckDuckGo web adapter 765a999](https://github.com/searxng/searxng/commit/765a9999dfde789c3b194c2474f86f3212675c36):
  selects Firefox impersonation without automatic browser headers, adds a
  JavaScript-challenge arithmetic parser and follow-up request, and handles empty
  result lists before accessing pagination. The shared online processor now
  forwards default_headers, including False, alongside existing curl options.
- [Startpage adapter 42e1d61](https://github.com/searxng/searxng/commit/42e1d61296bb686ee2ddfa0fab3984b50d844dd4):
  adds proof-of-work challenge handling and marks its variants inactive by
  default. Do not activate this as a side effect of a general image update.

## Applicability And Safety Decision

Our DuckDuckGo web entry is disabled by default; DuckDuckGo News remains enabled.
The new patch changes duckduckgo_web.py, not the duckduckgo_extra.py token-fetch
path traced in the failed News samples. The web first-page fetch also retains
its explicit 2s timeout. Therefore this is not an established News timeout fix.
The shared processor change requires review even if only the web engine is used.

The new web challenge handler constructs a follow-up with urljoin using a path
captured from the provider response, and forwards the engine headers. It does not
validate that resulting URL's host in that function. A local standard-library
probe confirmed that a normal relative path stays on the expected DDG host, but
absolute and scheme-relative synthetic foreign URLs replace the base host.
No request was sent; this checks URL-joining semantics, not the whole adapter or
an end-to-end exploit. Other networking controls were not evaluated for this new
path, and the result is not a claim that production AnonExplo is vulnerable.

Before considering this web adapter, define and test an explicit allowed HTTPS
origin for challenge follow-ups, redirect handling, bounded parsing and the shared
request budget. Preserve source guards, user-controlled engine choice and native
cooldowns. Do not execute challenge JavaScript, forward headers to arbitrary
origins, or assume successful offline parsing proves live reliability.

Production stays unchanged. Do not broadly update the image, enable DuckDuckGo
web/Startpage, or port Firefox settings into News as an inferred fix. This
follow-up found a distinct possible web-coverage candidate, not a validated repair
for the current issue. A hardened offline web-adapter experiment would be a
separate scope; no live challenge or fresh provider fixture is approved here.

## Verification And Closeout

Reviewed both exact upstream commit diffs and local engine selection. Local
URL-joining checks passed (one expected-host case and two foreign-host cases).
No upstream code was executed or imported. Full validate.ps1 passed: 80 baseline
Python tests, 20 negative Compose cases, seven negative identity cases plus
equality, source/binding checks, managed validation build with production tag
unchanged, privacy/settings/ranking, offline egress block, outage/recovery and
cleanup. Optional 0.16.3 comparison was not repeated: that result is unchanged
and irrelevant to this new source-only review.

Reviewed documentation accompanies commit/push, fast-forward main merge and
local/remote branch cleanup. No production deployment, image/config changes or
release. Next scope, if selected, is the hardened offline DDG web candidate;
it must not be presented as an established fix for DDG News.
