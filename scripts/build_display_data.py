#!/usr/bin/env python3
"""
Build display-ready, China-mainland-only ranking data, organised by
board -> source -> year so that every distinct dataset lives at its own URL.

Output tree (under public/eval/data/):

  manifest.json
  university/qs/index.json        -> { "years": [...], "default": "2027" }
  university/qs/2027.json         -> { year, source, count, indicators, list }
  university/usnews/index.json
  university/usnews/2026.json
  subject/cde/index.json          -> categorised disciplines (data/sources/cde_subject_eval.json)
  subject/qs/index.json           -> faculties/subjects   (data/sources/qs_subject.json)
  subject/usnews/index.json       -> categorised subjects  (raw_data/usnews/...)

Inputs:
  data/sources/qs_university.json     -> QS university per-year + indicators
  data/sources/the_university.json    -> THE university per-year, China mainland only
  data/sources/cde_subject_eval.json  -> CDE (China Discipline Evaluation) 4th round
  data/sources/qs_subject.json        -> QS subject rankings by faculty
  data/sources/the_subject.json       -> THE subject rankings by broad subject area
  raw_data/usnews/...                 -> U.S. News global + subject (original, gitignored)
"""
import json, os, re

ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW     = os.path.join(ROOT, "raw_data")           # original collected data (gitignored)
SOURCES = os.path.join(ROOT, "data", "sources")    # canonical processed build inputs
OUT     = os.path.join(ROOT, "public", "eval", "data")  # generated, published site data

def w(path, obj):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {path}  ({os.path.getsize(full)//1024} KB)")

def is_china(country_name, code):
    return code == "CHN" or (country_name or "").strip() in ("China", "China (Mainland)")

def num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None

def clean_rank(v):
    s = str(v or "").strip()
    return s.replace("=", "") if s else ""

# ────────────────────────────────────────────────────────────
# 1. UNIVERSITY · QS  (split the per-year file we already have)
# ────────────────────────────────────────────────────────────
def build_university_qs():
    print("University · QS")
    src = os.path.join(SOURCES, "qs_university.json")
    data = json.load(open(src, encoding="utf-8"))
    years = sorted(data.keys(), reverse=True)
    for y in years:
        yd = data[y]
        w(f"university/qs/{y}.json", {
            "year": y, "source": "qs",
            "count": yd["count"],
            "indicators": yd["indicators"],
            "list": yd["list"],
        })
    w("university/qs/index.json", {"source": "qs", "years": years, "default": years[0]})
    return years

# ────────────────────────────────────────────────────────────
# 2. UNIVERSITY · US News  (Best Global Universities)
# ────────────────────────────────────────────────────────────
def build_university_usnews():
    print("University · US News")
    src = os.path.join(RAW, "usnews", "global-universities",
                       "2026-2027", "usnews_global_universities_2026_2027.json")
    raw = json.load(open(src, encoding="utf-8"))
    rows = []
    for it in raw["items"]:
        if not is_china(it.get("country_name"), it.get("three_digit_country_code")):
            continue
        stats = {s["label"]: s["value"] for s in it.get("stats", [])}
        rk = it["ranks"][0] if it.get("ranks") else {}
        rows.append({
            "rank": clean_rank(rk.get("value")),
            "tied": bool(rk.get("is_tied")),
            "name": it["name"],
            "city": it.get("city", ""),
            "overall": num(stats.get("Global Score")),
            "enrollment": num(stats.get("Enrollment")),
        })
    rows.sort(key=lambda r: int(re.sub(r"\D", "", r["rank"]) or 10**9))
    year = "2026"   # the 2026-2027 edition
    w(f"university/usnews/{year}.json", {
        "year": year, "source": "usnews",
        "edition": "2026-2027",
        "count": len(rows),
        "indicators": [],           # this dataset exposes only Global Score
        "list": rows,
    })
    w("university/usnews/index.json",
      {"source": "usnews", "years": [year], "default": year,
       "editions": {year: "2026-2027"}})
    return [year]

# ────────────────────────────────────────────────────────────
# 3. UNIVERSITY · THE  (World University Rankings)
# ────────────────────────────────────────────────────────────
def build_university_the():
    print("University · THE")
    src = os.path.join(SOURCES, "the_university.json")
    data = json.load(open(src, encoding="utf-8"))
    years = sorted(data.keys(), reverse=True)
    for y in years:
        yd = data[y]
        w(f"university/the/{y}.json", {
            "year": y, "source": "the",
            "count": yd["count"],
            "indicators": yd["indicators"],
            "list": yd["list"],
        })
    w("university/the/index.json", {"source": "the", "years": years, "default": years[0]})
    return years

# ────────────────────────────────────────────────────────────
# 4. SUBJECT · MoE & QS  (copy existing static files into place)
# ────────────────────────────────────────────────────────────
def build_subject_cde():
    print("Subject · CDE")
    cde = json.load(open(os.path.join(SOURCES, "cde_subject_eval.json"), encoding="utf-8"))
    w("subject/cde/index.json", cde)

def build_subject_qs():
    print("Subject · QS")
    qs = json.load(open(os.path.join(SOURCES, "qs_subject.json"), encoding="utf-8"))
    w("subject/qs/index.json", qs)

# ────────────────────────────────────────────────────────────
# 5. SUBJECT · THE  (11 broad subject areas)
# ────────────────────────────────────────────────────────────
def build_subject_the():
    print("Subject · THE")
    data = json.load(open(os.path.join(SOURCES, "the_subject.json"), encoding="utf-8"))
    years = sorted(data.keys(), reverse=True)
    for y in years:
        yd = data[y]
        if "THE" in yd.get("categories", {}):
            yd["categories"]["THE"]["name_en"] = "Times Higher Education"
        w(f"subject/the/{y}.json", yd)
    w("subject/the/index.json", {"source": "the", "years": years, "default": years[0]})
    return years

# ────────────────────────────────────────────────────────────
# 6. SUBJECT · US News  (51 subjects -> grouped into categories)
# ────────────────────────────────────────────────────────────
USNEWS_CATEGORIES = [
    ("ENG", "Engineering & Materials", [
        "engineering", "chemical-engineering", "civil-engineering",
        "electrical-electronic-engineering", "mechanical-engineering",
        "environmental-engineering", "materials-science",
        "nanoscience-nanotechnology", "polymer-science", "energy-fuels",
        "green-sustainable-science-technology",
    ]),
    ("CS", "Computer Science & AI", [
        "computer-science", "artificial-intelligence",
    ]),
    ("PHYS", "Physical Sciences & Math", [
        "physics", "chemistry", "physical-chemistry", "condensed-matter-physics",
        "mathematics", "optics", "space-science", "geosciences",
        "meteorology-atmospheric-sciences",
    ]),
    ("LIFE", "Life & Agricultural Sciences", [
        "biology-biochemistry", "biotechnology-applied-microbiology",
        "cell-biology", "molecular-biology-genetics", "microbiology",
        "ecology", "marine-freshwater-biology", "plant-animal-science",
        "agricultural-sciences", "food-science-technology",
        "environment-ecology", "water-resources",
    ]),
    ("MED", "Medicine & Health", [
        "clinical-medicine", "cardiac-cardiovascular", "endocrinology-metabolism",
        "gastroenterology-hepatology", "immunology", "infectious-diseases",
        "neuroscience-behavior", "oncology", "pharmacology-toxicology",
        "psychiatry-psychology", "public-environmental-occupational-health",
        "radiology-nuclear-medicine-medical-imaging", "surgery",
    ]),
    ("SOC", "Social Sciences & Humanities", [
        "economics-business", "education-educational-research",
        "arts-and-humanities", "social-sciences-public-health",
    ]),
]

def build_subject_usnews():
    print("Subject · US News")
    src = os.path.join(RAW, "usnews", "subject-rankings",
                       "2026-2027", "usnews_subject_rankings_2026_2027.json")
    raw = json.load(open(src, encoding="utf-8"))
    names = {s["subject"]: s["subject_name"] for s in raw["subject_summaries"]}

    per_subject = {}
    for it in raw["items"]:
        if not is_china(it.get("country_name"), it.get("three_digit_country_code")):
            continue
        slug = it["subject"]
        per_subject.setdefault(slug, []).append({
            "institution": it["name"],
            "city": it.get("city", ""),
            "subject_rank": clean_rank(it.get("subject_rank")),
            "rank_tied": str(it.get("subject_rank_tied")).lower() == "true",
            "global_rank": clean_rank(it.get("global_rank")),
            "subject_score": num(it.get("subject_score")),
            "global_score": num(it.get("global_score")),
        })

    out = {}
    slug_to_cat = {}
    for code, label, slugs in USNEWS_CATEGORIES:
        for s in slugs:
            slug_to_cat[s] = code
        subjects = {}
        for slug in slugs:
            rows = per_subject.get(slug, [])
            rows.sort(key=lambda r: int(re.sub(r"\D", "", r["subject_rank"]) or 10**9))
            subjects[slug] = {
                "slug": slug,
                "name_en": names.get(slug, slug.replace("-", " ").title()),
                "list": rows,
            }
        out[code] = {"code": code, "name_en": label, "subjects": subjects}

    missing = [s for s in names if s not in slug_to_cat]
    if missing:
        print("  WARNING uncategorised:", missing)

    w("subject/usnews/index.json", {
        "source": "usnews", "edition": "2026-2027", "categories": out,
    })

# ────────────────────────────────────────────────────────────
def main():
    uni_qs_years = build_university_qs()
    uni_us_years = build_university_usnews()
    uni_the_years = build_university_the()
    build_subject_cde()
    build_subject_qs()
    subj_the_years = build_subject_the()
    build_subject_usnews()

    manifest = {
        "boards": {
            "university": {
                "label": "University Rankings",
                "default_source": "qs",
                "sources": {
                    "qs":     {"label": "QS",      "endpoint": "./data/university/qs",     "years": uni_qs_years, "default_year": uni_qs_years[0]},
                    "usnews": {"label": "US News", "endpoint": "./data/university/usnews", "years": uni_us_years, "default_year": uni_us_years[0]},
                    "the":    {"label": "THE",     "endpoint": "./data/university/the",    "years": uni_the_years, "default_year": uni_the_years[0]},
                },
            },
            "subject": {
                "label": "Subject Rankings",
                "default_source": "cde",
                "sources": {
                    "cde":    {"label": "CDE", "endpoint": "./data/subject/cde/index.json", "years": ["2016"], "default_year": "2016"},
                    "qs":     {"label": "QS",             "endpoint": "./data/subject/qs/index.json",     "years": ["2026"], "default_year": "2026"},
                    "usnews": {"label": "US News",        "endpoint": "./data/subject/usnews/index.json", "years": ["2026"], "default_year": "2026"},
                    "the":    {"label": "THE",            "endpoint": "./data/subject/the", "years": subj_the_years, "default_year": subj_the_years[0]},
                },
            },
        }
    }
    w("manifest.json", manifest)
    print("Done.")

if __name__ == "__main__":
    main()
