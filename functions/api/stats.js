// CF Pages Function: real-time GitHub stats for the plugin directory.
// Endpoint: /api/stats  ->  { "<plugin>": {"stars": N, "forks": N, "issues": N} }
import repos from './repos.json' with { type: 'json' };

export async function onRequest(context) {
  const { env } = context;
  const token = env.GITHUB_TOKEN;
  const cache = caches.default;
  const cacheKey = new Request('https://dshbase-stats-cache.local/stats');

  // Serve from cache if fresh (< 1 hour)
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const entries = Object.entries(repos);
  const out = {};
  const headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'dshbase-stats',
    ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
  };

  // Batch fetch GitHub repos (parallel, capped)
  await Promise.all(entries.map(async ([name, repo]) => {
    try {
      const r = await fetch('https://api.github.com/repos/' + repo, { headers });
      if (r.ok) {
        const d = await r.json();
        out[name] = {
          stars: d.stargazers_count ?? 0,
          forks: d.forks_count ?? 0,
          issues: d.open_issues_count ?? 0,
        };
      }
    } catch (e) {
      // skip on error; front-end falls back to static value
    }
  }));

  const response = new Response(JSON.stringify(out), {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=3600',
    },
  });
  await cache.put(cacheKey, response.clone());
  return response;
}
