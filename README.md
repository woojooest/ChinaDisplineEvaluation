# Discipline Evaluation Query

A static Cloudflare Pages site. Three-pane master-detail layout:
left = broad categories, middle = subjects, right = results grouped by grade (A+ first).

## Structure

```
public/
  eval/
    index.html        the query UI       -> /eval
    data/eval.json    your ~2MB dataset  (REPLACE the sample with your real file)
functions/
  api/health.js       sample API         -> /api/health  (for future services)
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
# ChinaDisplineEvaluation
