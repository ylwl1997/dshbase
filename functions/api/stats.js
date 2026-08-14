export async function onRequest() {
  const cache = caches.default;
  const key = new Request('https://dshbase-stats.local/v1');
  const cached = await cache.match(key);
  if (cached) return cached;
  const res = new Response(JSON.stringify({ cached: false }), { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
  await cache.put(key, res.clone());
  return res;
}
