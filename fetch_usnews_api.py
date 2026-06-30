#!/usr/bin/env python3
import json
import os
import sys

from curl_cffi import requests


API_URL = (
    "https://www.usnews.com/education/best-global-universities/api/search"
    "?_page=1&_sort=rank&_sortDirection=asc"
)
REFERER = "https://www.usnews.com/education/best-global-universities/rankings"


def main() -> int:
    proxy = os.environ.get("USNEWS_PROXY", "socks5://127.0.0.1:62809")
    proxies = {"http": proxy, "https": proxy}

    session = requests.Session(impersonate="chrome")
    session.proxies = proxies
    session.headers.update(
        {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "referer": REFERER,
        }
    )

    print(f"proxy: {proxy}")
    print("warming up rankings page...")
    warmup = session.get(REFERER, timeout=45)
    print(f"rankings status: {warmup.status_code}")

    print("fetching api...")
    response = session.get(API_URL, timeout=45)
    print(f"api status: {response.status_code}")
    print(f"content-type: {response.headers.get('content-type')}")
    print(f"body bytes: {len(response.content)}")

    response.raise_for_status()
    data = response.json()

    print("\njson top-level keys:")
    print(", ".join(data.keys()) if isinstance(data, dict) else type(data).__name__)

    if isinstance(data, dict):
        items = data.get("items") or data.get("data") or data.get("results") or []
        if isinstance(items, list):
            print(f"\nitems: {len(items)}")
            for item in items[:3]:
                print(json.dumps(item, ensure_ascii=False)[:1000])
        else:
            print("\nbody preview:")
            print(json.dumps(data, ensure_ascii=False)[:2000])
    else:
        print("\nbody preview:")
        print(json.dumps(data, ensure_ascii=False)[:2000])

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise
