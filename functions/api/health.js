// Example API endpoint for future expansion.
//   GET  tools.yourdomain.com/api/health
// File path = route. Add more files under functions/ as you add services.
// Static assets and these functions share the same domain with no extra config.
export async function onRequest(context) {
  return Response.json({
    ok: true,
    service: "eval-query",
    time: new Date().toISOString(),
  });
}

