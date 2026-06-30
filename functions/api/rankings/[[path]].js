// Unified rankings API. Every distinct dataset has its OWN endpoint URL:
//
//   /api/rankings/university/qs              -> { years, default }
//   /api/rankings/university/qs/2027         -> { year, count, indicators, list }
//   /api/rankings/university/usnews          -> { years, default }
//   /api/rankings/university/usnews/2026     -> { ... }
//   /api/rankings/subject/cde                -> categorised disciplines
//   /api/rankings/subject/qs                 -> faculties / subjects
//   /api/rankings/subject/usnews             -> categorised subjects
//
// The data itself is the static JSON under /eval/data/<board>/<source>/...,
// so there is a single source of truth; this function just maps clean API
// paths onto those files (and validates the route).
const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "public, max-age=3600",
  "access-control-allow-origin": "*",
};

const ROUTES = {
  university: {
    qs:     "university/qs",
    usnews: "university/usnews",
  },
  subject: {
    cde:    "subject/cde",
    qs:     "subject/qs",
    usnews: "subject/usnews",
  },
};

function err(status, msg) {
  return Response.json({ error: msg }, { status, headers: JSON_HEADERS });
}

export async function onRequest(context) {
  const parts = (context.params.path || []).filter(Boolean); // [board, source, year?]
  const [board, source, year] = parts;

  if (!board || !ROUTES[board])            return err(404, `Unknown board: ${board || "(none)"}`);
  if (!source || !ROUTES[board][source])   return err(404, `Unknown source: ${source || "(none)"}`);

  const base = ROUTES[board][source];
  const origin = new URL(context.request.url).origin;

  // University: index unless a year is given. Subject: always the single index.
  let file;
  if (board === "university") {
    file = year ? `${base}/${year}.json` : `${base}/index.json`;
  } else {
    file = `${base}/index.json`;
  }

  const assetUrl = `${origin}/eval/data/${file}`;
  const res = await fetch(assetUrl, { cf: { cacheTtl: 3600 } });
  if (!res.ok) return err(404, `No data at ${file}`);

  const body = await res.text();
  return new Response(body, { headers: JSON_HEADERS });
}
