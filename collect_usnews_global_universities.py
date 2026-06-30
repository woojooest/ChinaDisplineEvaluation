#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from curl_cffi import requests


BASE_URL = "https://www.usnews.com/education/best-global-universities/api/search"
REFERER = "https://www.usnews.com/education/best-global-universities/rankings"
DEFAULT_PROXY = "socks5://127.0.0.1:62809"


def build_url(page: int) -> str:
    query = urlencode(
        {
            "page": page,
            "_sort": "rank",
            "_sortDirection": "asc",
        }
    )
    return f"{BASE_URL}?{query}"


def make_session(proxy: str) -> requests.Session:
    session = requests.Session(impersonate="chrome")
    session.proxies = {"http": proxy, "https": proxy}
    session.headers.update(
        {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "referer": REFERER,
        }
    )
    return session


def fetch_json(session: requests.Session, url: str, retries: int) -> dict:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            wait_seconds = 10 * (attempt + 1)
            print(
                f"request failed: {exc.__class__.__name__}: {exc}; "
                f"retrying in {wait_seconds}s",
                flush=True,
            )
            time.sleep(wait_seconds)
    raise RuntimeError(f"request failed after {retries + 1} attempts: {last_error}")


def rank_value(item: dict) -> str:
    ranks = item.get("ranks") or []
    if not ranks:
        return ""
    return str(ranks[0].get("value", ""))


def stat_value(item: dict, label: str) -> str:
    for stat in item.get("stats") or []:
        if stat.get("label") == label:
            return str(stat.get("value", ""))
    return ""


def write_outputs(payload: dict, items: list[dict], out_prefix: Path) -> None:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    json_path = out_prefix.with_suffix(".json")
    csv_path = out_prefix.with_suffix(".csv")

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    fieldnames = [
        "rank",
        "id",
        "name",
        "city",
        "country_name",
        "three_digit_country_code",
        "global_score",
        "enrollment",
        "url",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "rank": rank_value(item),
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "city": item.get("city", ""),
                    "country_name": item.get("country_name", ""),
                    "three_digit_country_code": item.get("three_digit_country_code", ""),
                    "global_score": stat_value(item, "Global Score"),
                    "enrollment": stat_value(item, "Enrollment"),
                    "url": item.get("url", ""),
                }
            )

    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")


def append_page(jsonl_path: Path, page: int, url: str, data: dict) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "page": page,
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "current_page": data.get("current_page"),
        "item_count": len(data.get("items") or []),
        "data": data,
    }
    with jsonl_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())


def load_page_records(jsonl_path: Path) -> dict[int, dict]:
    records = {}
    if not jsonl_path.exists():
        return records

    with jsonl_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"skipping invalid jsonl line {line_number}: {jsonl_path}", file=sys.stderr)
                continue

            page = record.get("page")
            data = record.get("data")
            if not isinstance(page, int) or not isinstance(data, dict):
                print(f"skipping malformed jsonl line {line_number}: {jsonl_path}", file=sys.stderr)
                continue
            records[page] = record
    return records


def merge_records(records: dict[int, dict], out_prefix: Path) -> None:
    if not records:
        raise RuntimeError("no page records to merge")

    pages = [records[page]["data"] for page in sorted(records)]
    first_page = pages[0]
    items = []
    for page_data in pages:
        items.extend(page_data.get("items") or [])

    total_count = int(first_page.get("total_count", len(items)))
    total_pages = int(first_page.get("total_pages", len(pages)))
    ids = [item.get("id") for item in items if item.get("id") is not None]

    payload = {
        "source": BASE_URL,
        "referer": REFERER,
        "sort": "rank",
        "sortDirection": "asc",
        "total_count": total_count,
        "total_pages": total_pages,
        "collected_pages": len(pages),
        "collected_items": len(items),
        "unique_item_ids": len(set(ids)),
        "duplicate_item_ids": len(ids) - len(set(ids)),
        "items": items,
        "pages": pages,
    }
    write_outputs(payload, items, out_prefix)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy", default=os.environ.get("USNEWS_PROXY", DEFAULT_PROXY))
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--out-prefix",
        default="raw_data/usnews/global-universities/2026-2027/usnews_global_universities_2026_2027",
    )
    parser.add_argument(
        "--jsonl-path",
        default=None,
        help="Page-level checkpoint file. Defaults to OUT_PREFIX.pages.jsonl.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete the checkpoint jsonl before collecting.",
    )
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Only merge the existing checkpoint jsonl into JSON/CSV.",
    )
    args = parser.parse_args()

    out_prefix = Path(args.out_prefix)
    jsonl_path = Path(args.jsonl_path) if args.jsonl_path else out_prefix.with_suffix(".pages.jsonl")

    if args.fresh and jsonl_path.exists():
        jsonl_path.unlink()
        print(f"deleted checkpoint {jsonl_path}")

    existing_records = load_page_records(jsonl_path)
    if args.merge_only:
        merge_records(existing_records, out_prefix)
        return 0

    session = make_session(args.proxy)

    print(f"proxy: {args.proxy}")
    print(f"checkpoint: {jsonl_path}")
    print("warming up rankings page...")
    warmup = session.get(REFERER, timeout=60)
    print(f"rankings status: {warmup.status_code}")
    warmup.raise_for_status()

    if 1 in existing_records:
        print("using page 1 from checkpoint for pagination metadata...")
        first_page = existing_records[1]["data"]
    else:
        print("fetching page 1 for pagination metadata...")
        first_page_url = build_url(1)
        first_page = fetch_json(session, first_page_url, args.retries)
        append_page(jsonl_path, 1, first_page_url, first_page)
        existing_records[1] = {
            "page": 1,
            "url": first_page_url,
            "data": first_page,
        }

    total_pages = int(first_page["total_pages"])
    total_count = int(first_page["total_count"])
    print(f"total_count: {total_count}; total_pages: {total_pages}")

    last_page = total_pages
    if args.max_pages is not None:
        last_page = min(total_pages, args.start_page + args.max_pages - 1)

    for page in range(args.start_page, last_page + 1):
        if page in existing_records:
            data = existing_records[page]["data"]
            print(f"page {page}/{total_pages}: already collected ({len(data.get('items') or [])} items)")
            continue
        print(f"sleeping {args.delay:.1f}s before page {page}...", flush=True)
        time.sleep(args.delay)
        page_url = build_url(page)
        page_data = fetch_json(session, page_url, args.retries)
        page_items = page_data.get("items") or []
        append_page(jsonl_path, page, page_url, page_data)
        existing_records[page] = {
            "page": page,
            "url": page_url,
            "data": page_data,
        }
        print(f"page {page}/{total_pages}: {len(page_items)} items", flush=True)

    records = load_page_records(jsonl_path)
    merge_records(records, out_prefix)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise
