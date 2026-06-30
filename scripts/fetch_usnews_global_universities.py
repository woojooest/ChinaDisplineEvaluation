#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

import requests


API_URL = "https://www.usnews.com/education/best-global-universities/api/search"
SOURCE_URL = "https://www.usnews.com/education/best-global-universities/rankings"
RELEASE_URL = "https://www.prnewswire.com/news-releases/us-news-unveils-2026-2027-best-global-universities-rankings-302800745.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": SOURCE_URL,
}

FIELDS = [
    "rank",
    "name",
    "city",
    "state",
    "country",
    "global_score",
    "source_url",
]

TOP_10_2026_2027 = [
    {"rank": 1, "name": "Harvard University", "city": "Cambridge", "state": "Massachusetts", "country": "United States"},
    {"rank": 2, "name": "Massachusetts Institute of Technology (MIT)", "city": "Cambridge", "state": "Massachusetts", "country": "United States"},
    {"rank": 3, "name": "Stanford University", "city": "Stanford", "state": "California", "country": "United States"},
    {"rank": 4, "name": "University of Oxford", "city": "Oxford", "state": "", "country": "United Kingdom"},
    {"rank": 5, "name": "University of Cambridge", "city": "Cambridge", "state": "", "country": "United Kingdom"},
    {"rank": 6, "name": "Tsinghua University", "city": "Beijing", "state": "", "country": "China"},
    {"rank": 7, "name": "University of California Berkeley", "city": "Berkeley", "state": "California", "country": "United States"},
    {"rank": 8, "name": "Yale University", "city": "New Haven", "state": "Connecticut", "country": "United States"},
    {"rank": 9, "name": "University College London", "city": "London", "state": "", "country": "United Kingdom"},
    {"rank": 10, "name": "Columbia University", "city": "New York City", "state": "New York", "country": "United States"},
]


def traverse(root, path):
    value = root
    for segment in path.split("."):
        if value is None:
            return None
        if segment.isdigit():
            index = int(segment)
            value = value[index] if isinstance(value, list) and len(value) > index else None
        elif isinstance(value, dict):
            value = value.get(segment)
        else:
            return None
    return value


def first_value(root, paths):
    for path in paths:
        value = traverse(root, path)
        if value not in (None, ""):
            return value
    return None


def normalize_item(item):
    return {
        "rank": first_value(item, ["ranking.sortRank", "ranking.rank", "rank", "sortRank"]),
        "name": first_value(item, ["institution.displayName", "institution.name", "displayName", "name"]),
        "city": first_value(item, ["institution.city", "city"]),
        "state": first_value(item, ["institution.state", "state"]),
        "country": first_value(item, ["institution.country", "country"]),
        "global_score": first_value(item, ["searchData.globalScore.rawValue", "score", "globalScore"]),
        "source_url": SOURCE_URL,
    }


def fetch_from_api(limit):
    rows = []
    page = 1

    while len(rows) < limit:
        response = requests.get(
            API_URL,
            params={"_page": page, "_sort": "rank", "_sortDirection": "asc"},
            headers=HEADERS,
            timeout=(5, 15),
        )
        response.raise_for_status()
        payload = response.json()
        items = traverse(payload, "data.items") or []
        if not items:
            break

        rows.extend(normalize_item(item) for item in items)
        next_url = traverse(payload, "meta.rel_next_page_url")
        if not next_url:
            break
        page += 1

    return rows[:limit]


def fallback_rows(limit):
    rows = []
    for row in TOP_10_2026_2027[:limit]:
        rows.append({**row, "global_score": None, "source_url": RELEASE_URL})
    return rows


def write_outputs(rows, output_base):
    json_path = output_base.with_suffix(".json")
    csv_path = output_base.with_suffix(".csv")

    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", default="public/eval/data/usnews_best_global_universities_top10")
    parser.add_argument("--no-fallback", action="store_true")
    args = parser.parse_args()

    try:
        rows = fetch_from_api(args.limit)
        source = "api"
    except requests.RequestException as exc:
        if args.no_fallback:
            raise
        print(f"USNews API request failed, using release fallback: {exc}")
        rows = fallback_rows(args.limit)
        source = "fallback"

    json_path, csv_path = write_outputs(rows, Path(args.output))
    print(f"Wrote {len(rows)} rows from {source}: {json_path}, {csv_path}")


if __name__ == "__main__":
    main()
