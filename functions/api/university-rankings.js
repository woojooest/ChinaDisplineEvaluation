// University ranking endpoint (separate from the static eval data).
//   GET /api/university-rankings            -> { years: [...], default: "<newest>" }
//   GET /api/university-rankings?year=2027  -> { year, count, indicators, list }
//
// Data is bundled into the function (university-data.json) so it is served only
// through this endpoint. Only mainland China institutions are included.
import DATA from "./university-data.json";

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "public, max-age=3600",
  "access-control-allow-origin": "*",
};

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const year = url.searchParams.get("year");
  const years = Object.keys(DATA).sort().reverse();

  if (!year) {
    return Response.json({ years, default: years[0] }, { headers: JSON_HEADERS });
  }

  const yd = DATA[year];
  if (!yd) {
    return Response.json(
      { error: `No data for year ${year}`, years },
      { status: 404, headers: JSON_HEADERS }
    );
  }

  return Response.json({ year, ...yd }, { headers: JSON_HEADERS });
}
