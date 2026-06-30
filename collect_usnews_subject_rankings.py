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

SUBJECTS = {
    "agricultural-sciences": "Agricultural Sciences",
    "artificial-intelligence": "Artificial Intelligence",
    "arts-and-humanities": "Arts and Humanities",
    "biology-biochemistry": "Biology and Biochemistry",
    "biotechnology-applied-microbiology": "Biotechnology and Applied Microbiology",
    "cardiac-cardiovascular": "Cardiac and Cardiovascular Systems",
    "cell-biology": "Cell Biology",
    "chemical-engineering": "Chemical Engineering",
    "chemistry": "Chemistry",
    "civil-engineering": "Civil Engineering",
    "clinical-medicine": "Clinical Medicine",
    "computer-science": "Computer Science",
    "condensed-matter-physics": "Condensed Matter Physics",
    "ecology": "Ecology",
    "economics-business": "Economics and Business",
    "education-educational-research": "Education and Educational Research",
    "electrical-electronic-engineering": "Electrical and Electronic Engineering",
    "endocrinology-metabolism": "Endocrinology and Metabolism",
    "energy-fuels": "Energy and Fuels",
    "engineering": "Engineering",
    "environment-ecology": "Environment/Ecology",
    "environmental-engineering": "Environmental/Engineering",
    "food-science-technology": "Food Science and Technology",
    "gastroenterology-hepatology": "Gastroenterology and Hepatology",
    "geosciences": "Geosciences",
    "green-sustainable-science-technology": "Green and Sustainable Science and Technology",
    "immunology": "Immunology",
    "infectious-diseases": "Infectious Diseases",
    "marine-freshwater-biology": "Marine and Freshwater Biology",
    "materials-science": "Materials Science",
    "mathematics": "Mathematics",
    "mechanical-engineering": "Mechanical Engineering",
    "meteorology-atmospheric-sciences": "Meteorology and Atmospheric Sciences",
    "microbiology": "Microbiology",
    "molecular-biology-genetics": "Molecular Biology and Genetics",
    "nanoscience-nanotechnology": "Nanoscience and Nanotechnology",
    "neuroscience-behavior": "Neuroscience and Behavior",
    "oncology": "Oncology",
    "optics": "Optics",
    "pharmacology-toxicology": "Pharmacology and Toxicology",
    "physical-chemistry": "Physical Chemistry",
    "physics": "Physics",
    "plant-animal-science": "Plant and Animal Science",
    "polymer-science": "Polymer Science",
    "psychiatry-psychology": "Psychiatry/Psychology",
    "public-environmental-occupational-health": "Public, Environmental and Occupational Health",
    "radiology-nuclear-medicine-medical-imaging": "Radiology, Nuclear Medicine and Medical Imaging",
    "social-sciences-public-health": "Social Sciences and Public Health",
    "space-science": "Space Science",
    "surgery": "Surgery",
    "water-resources": "Water Resources",
}


def build_url(page: int, subject: str, country: str | None = None) -> str:
    query = {
        "page": page,
        "_sort": "rank",
        "_sortDirection": "asc",
        "subject": subject,
    }
    if country:
        query["country"] = country
    return f"{BASE_URL}?{urlencode(query)}"


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


def rank_value(item: dict, label_prefix: str) -> str:
    for rank in item.get("ranks") or []:
        label = rank.get("label") or ""
        if label.startswith(label_prefix):
            return str(rank.get("value", ""))
    return ""


def rank_tied(item: dict, label_prefix: str) -> str:
    for rank in item.get("ranks") or []:
        label = rank.get("label") or ""
        if label.startswith(label_prefix):
            return str(bool(rank.get("is_tied", False))).lower()
    return ""


def stat_value(item: dict, label: str) -> str:
    for stat in item.get("stats") or []:
        if stat.get("label") == label:
            return str(stat.get("value", ""))
    return ""


def page_record_key(subject: str, country: str | None, page: int) -> str:
    return f"{subject}:{country or ''}:{page}"


def append_page(
    jsonl_path: Path,
    subject: str,
    country: str | None,
    page: int,
    url: str,
    data: dict,
) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "subject": subject,
        "subject_name": SUBJECTS.get(subject, subject),
        "country": country or "",
        "page": page,
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "current_page": data.get("current_page"),
        "item_count": len(data.get("items") or []),
        "total_count": data.get("total_count"),
        "total_pages": data.get("total_pages"),
        "data": data,
    }
    with jsonl_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())


def load_page_records(jsonl_path: Path) -> dict[str, dict]:
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

            subject = record.get("subject")
            country = record.get("country") or ""
            page = record.get("page")
            data = record.get("data")
            if not isinstance(subject, str) or not isinstance(page, int) or not isinstance(data, dict):
                print(f"skipping malformed jsonl line {line_number}: {jsonl_path}", file=sys.stderr)
                continue
            records[page_record_key(subject, country, page)] = record
    return records


def write_outputs(payload: dict, rows: list[dict], out_prefix: Path) -> None:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    json_path = out_prefix.with_suffix(".json")
    csv_path = out_prefix.with_suffix(".csv")

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    fieldnames = [
        "subject",
        "subject_name",
        "subject_rank",
        "subject_rank_tied",
        "global_rank",
        "id",
        "name",
        "city",
        "country_name",
        "three_digit_country_code",
        "subject_score",
        "global_score",
        "enrollment",
        "url",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")


def merge_records(records: dict[str, dict], subjects: list[str], out_prefix: Path, country: str | None) -> None:
    selected_records = [
        record
        for record in records.values()
        if record.get("subject") in subjects and (record.get("country") or "") == (country or "")
    ]
    if not selected_records:
        raise RuntimeError("no page records to merge")

    selected_records.sort(key=lambda record: (subjects.index(record["subject"]), record["page"]))

    rows = []
    pages = []
    subject_summaries = {}
    ids = []
    for record in selected_records:
        subject = record["subject"]
        data = record["data"]
        pages.append(data)
        subject_summaries.setdefault(
            subject,
            {
                "subject": subject,
                "subject_name": SUBJECTS.get(subject, subject),
                "total_count": data.get("total_count"),
                "total_pages": data.get("total_pages"),
                "collected_pages": 0,
                "collected_items": 0,
            },
        )
        subject_summaries[subject]["collected_pages"] += 1

        for item in data.get("items") or []:
            if item.get("id") is not None:
                ids.append(f"{subject}:{item.get('id')}")
            subject_summaries[subject]["collected_items"] += 1
            rows.append(
                {
                    "subject": subject,
                    "subject_name": SUBJECTS.get(subject, subject),
                    "subject_rank": rank_value(item, "Best Universities for "),
                    "subject_rank_tied": rank_tied(item, "Best Universities for "),
                    "global_rank": rank_value(item, "Best Global Universities"),
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "city": item.get("city", ""),
                    "country_name": item.get("country_name", ""),
                    "three_digit_country_code": item.get("three_digit_country_code", ""),
                    "subject_score": stat_value(item, "Subject Score"),
                    "global_score": stat_value(item, "Global Score"),
                    "enrollment": stat_value(item, "Enrollment"),
                    "url": item.get("url", ""),
                }
            )

    payload = {
        "source": BASE_URL,
        "referer": REFERER,
        "sort": "rank",
        "sortDirection": "asc",
        "country": country or "",
        "subjects": subjects,
        "subject_summaries": list(subject_summaries.values()),
        "collected_pages": len(selected_records),
        "collected_items": len(rows),
        "unique_subject_item_ids": len(set(ids)),
        "duplicate_subject_item_ids": len(ids) - len(set(ids)),
        "items": rows,
        "pages": pages,
    }
    write_outputs(payload, rows, out_prefix)


def parse_subjects(args: argparse.Namespace) -> list[str]:
    if args.all_subjects:
        return list(SUBJECTS)
    subjects = args.subject or []
    invalid_subjects = [subject for subject in subjects if subject not in SUBJECTS]
    if invalid_subjects:
        valid = ", ".join(SUBJECTS)
        raise ValueError(f"unknown subject(s): {', '.join(invalid_subjects)}; valid subjects: {valid}")
    if not subjects:
        raise ValueError("provide --subject SUBJECT or --all-subjects")
    return subjects


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", action="append", choices=sorted(SUBJECTS))
    parser.add_argument("--all-subjects", action="store_true")
    parser.add_argument("--country", default=None, help="Optional US News country slug, e.g. united-states.")
    parser.add_argument("--proxy", default=os.environ.get("USNEWS_PROXY", DEFAULT_PROXY))
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--out-prefix",
        default="raw_data/usnews/subject-rankings/2026-2027/usnews_subject_rankings_2026_2027",
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

    subjects = parse_subjects(args)
    out_prefix = Path(args.out_prefix)
    jsonl_path = Path(args.jsonl_path) if args.jsonl_path else out_prefix.with_suffix(".pages.jsonl")

    if args.fresh and jsonl_path.exists():
        jsonl_path.unlink()
        print(f"deleted checkpoint {jsonl_path}")

    existing_records = load_page_records(jsonl_path)
    if args.merge_only:
        merge_records(existing_records, subjects, out_prefix, args.country)
        return 0

    session = make_session(args.proxy)

    print(f"proxy: {args.proxy}")
    print(f"checkpoint: {jsonl_path}")
    print(f"subjects: {', '.join(subjects)}")
    if args.country:
        print(f"country: {args.country}")
    print("warming up rankings page...")
    warmup = session.get(REFERER, timeout=60)
    print(f"rankings status: {warmup.status_code}")
    warmup.raise_for_status()

    for subject in subjects:
        first_key = page_record_key(subject, args.country, 1)
        if first_key in existing_records:
            print(f"{subject}: using page 1 from checkpoint for pagination metadata...")
            first_page = existing_records[first_key]["data"]
        else:
            print(f"{subject}: fetching page 1 for pagination metadata...")
            first_page_url = build_url(1, subject, args.country)
            first_page = fetch_json(session, first_page_url, args.retries)
            append_page(jsonl_path, subject, args.country, 1, first_page_url, first_page)
            existing_records[first_key] = {
                "subject": subject,
                "country": args.country or "",
                "page": 1,
                "url": first_page_url,
                "data": first_page,
            }

        total_pages = int(first_page["total_pages"])
        total_count = int(first_page["total_count"])
        print(f"{subject}: total_count: {total_count}; total_pages: {total_pages}")

        last_page = total_pages
        if args.max_pages is not None:
            last_page = min(total_pages, args.start_page + args.max_pages - 1)

        for page in range(args.start_page, last_page + 1):
            record_key = page_record_key(subject, args.country, page)
            if record_key in existing_records:
                data = existing_records[record_key]["data"]
                print(
                    f"{subject} page {page}/{total_pages}: "
                    f"already collected ({len(data.get('items') or [])} items)"
                )
                continue
            print(f"sleeping {args.delay:.1f}s before {subject} page {page}...", flush=True)
            time.sleep(args.delay)
            page_url = build_url(page, subject, args.country)
            page_data = fetch_json(session, page_url, args.retries)
            page_items = page_data.get("items") or []
            append_page(jsonl_path, subject, args.country, page, page_url, page_data)
            existing_records[record_key] = {
                "subject": subject,
                "country": args.country or "",
                "page": page,
                "url": page_url,
                "data": page_data,
            }
            print(f"{subject} page {page}/{total_pages}: {len(page_items)} items", flush=True)

    records = load_page_records(jsonl_path)
    merge_records(records, subjects, out_prefix, args.country)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise
