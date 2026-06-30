# Discipline Evaluation Query

A static Cloudflare Pages site. Three-pane master-detail layout:
left = broad categories, middle = subjects, right = results grouped by grade (A+ first).

## Structure

```
public/                              PUBLISHED site (Output directory = public)
  eval/
    index.html                       the query UI                    -> /eval
    data/
      manifest.json                  boards / sources / years
      university/qs/<year>.json       QS world university rankings
      university/usnews/<year>.json   U.S. News Best Global Universities
      subject/cde/index.json          China Discipline Evaluation (CDE)
      subject/qs/index.json           QS rankings by subject
      subject/usnews/index.json       U.S. News rankings by subject
functions/
  api/health.js                      sample API                      -> /api/health
  api/rankings/[[path]].js           rankings API (one URL per dataset)

data/sources/                        canonical processed build inputs (committed)
  qs_university.json                 QS university per-year + indicators
  cde_subject_eval.json              CDE 4th round (2016)
  qs_subject.json                    QS subject rankings
raw_data/                            ORIGINAL collected data (gitignored): QS xlsx, U.S. News, ...
data/the/                            Times Higher Education raw pulls (not yet used by the site)
archive/                             superseded / intermediate files, kept for reference
scripts/build_display_data.py        rebuilds public/eval/data/** from data/sources + raw_data
```

Every distinct dataset (board × source × year) loads from its own URL, both as a
static file under `data/...` and via `/api/rankings/<board>/<source>/<year>`.

Rebuild the published data after changing any input:

```bash
python3 scripts/build_display_data.py
```

To add more services later, drop another folder under `public/` (e.g.
`public/another/index.html` → `/another`), or another file under `functions/`.

## Deploy

### Option A — Git (recommended, auto-deploy on push)
1. Push this repo to GitHub.
2. Cloudflare Dashboard → Workers & Pages → Create → Pages → connect repo.
3. Build settings: Framework = None, build command = empty,
   **Output directory = `public`**.

### Option B — CLI
```bash
npm i -g wrangler
wrangler pages deploy public --project-name=eval-query
```

## Subdomain + subpath

- Subdomain: Pages project → Custom domains → add `tools.yourdomain.com`
  (DNS auto-configured since the domain is on Cloudflare).
- The UI lives at `tools.yourdomain.com/eval`. Each future service is just
  another subfolder, all served from the same domain.

## Notes

- The 2MB JSON loads once into the browser; all filtering is client-side.
- Grade order: A+, A, A-, B+, B, B-, C+, C, C-. Ties broken by institution code.
- If the dataset grows to tens of MB, move querying server-side via a Function
  reading from D1 (SQLite) or KV instead of shipping the whole file.

## US News data scripts

Raw data is organized as:

```text
raw_data/
  qs/
    world-university-rankings/
      2024/
      2025/
      2026/
      2027/
  usnews/
    global-universities/
      2026-2027/
    subject-rankings/
      2026-2027/
```

Collect overall Best Global Universities rankings:

```bash
python3 collect_usnews_global_universities.py --fresh
```

Collect one US News subject ranking:

```bash
python3 collect_usnews_subject_rankings.py --subject computer-science --fresh
```

Collect all 51 subject rankings:

```bash
python3 collect_usnews_subject_rankings.py --all-subjects --fresh
```

Limit to a country by US News country slug:

```bash
python3 collect_usnews_subject_rankings.py --subject computer-science --country united-states --fresh
```
# ChinaDisplineEvaluation
