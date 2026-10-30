#!/usr/bin/env python3
"""Low-volume, explicitly identified security-protection probe.

Sends only GET requests, never follows redirects, and stops immediately on
an authorization/rate-limit response. Use only against an endpoint you own
or are authorized to test. This is not an evasion or load-testing tool.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

MAX_REQUESTS = 10
MIN_INTERVAL_SECONDS = 5.0
RELEVANT_HEADERS = (
    "Retry-After",
    "RateLimit-Limit",
    "RateLimit-Remaining",
    "RateLimit-Reset",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
    "Server",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe an authorized endpoint with a small number of labeled GET requests."
    )
    parser.add_argument("url", help="HTTPS endpoint on your own site or test environment")
    parser.add_argument("--requests", type=int, default=5,
                        help="1–10 requests; default: 5")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="fixed seconds between requests; minimum: 5")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme != "https" or not parsed.netloc:
        parser.error("URL must be a complete HTTPS URL")
    if not 1 <= args.requests <= MAX_REQUESTS:
        parser.error(f"--requests must be between 1 and {MAX_REQUESTS}")
    if args.interval < MIN_INTERVAL_SECONDS:
        parser.error(f"--interval must be at least {MIN_INTERVAL_SECONDS:g} seconds")

    opener = urllib.request.build_opener(NoRedirect)
    headers = {
        "User-Agent": "Authorized-Security-Protection-Probe/1.0",
        "X-Security-Test": "authorized-low-volume-probe",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
    }
    safe_target = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
    print(f"Target: {safe_target}")
    print(f"Plan: up to {args.requests} GET requests, {args.interval:g}s apart; no redirects.")
    print("The probe stops on HTTP 401, 403, 429, 3xx, or 5xx responses.\n")

    for number in range(1, args.requests + 1):
        request = urllib.request.Request(args.url, headers=headers, method="GET")
        started = time.monotonic()
        try:
            with opener.open(request, timeout=15) as response:
                status = response.status
                response_headers = response.headers
        except urllib.error.HTTPError as error:
            status = error.code
            response_headers = error.headers
        except (urllib.error.URLError, TimeoutError) as error:
            elapsed = time.monotonic() - started
            print(f"{number}: request error after {elapsed:.2f}s: {error}")
            print("Stopping to avoid repeated traffic after a network error.")
            return 2

        elapsed = time.monotonic() - started
        print(f"{number}: HTTP {status} in {elapsed:.2f}s")
        for name in RELEVANT_HEADERS:
            value = response_headers.get(name)
            if value is not None:
                print(f"  {name}: {value}")

        if status == 429:
            print(f"\nRate limit observed at request {number}; stopping. Honor Retry-After.")
            return 0
        if status in (401, 403):
            print(f"\nAccess denial/challenge observed at request {number}; stopping.")
            return 0
        if 300 <= status < 400:
            print("\nRedirect observed; not following it. Stopping.")
            return 0
        if status >= 500:
            print("\nServer error observed; stopping to limit impact.")
            return 0
        if number < args.requests:
            time.sleep(args.interval)

    print(f"\nNo 401/403/429 response observed in {args.requests} requests.")
    print("This small sample does not prove that protections are absent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
