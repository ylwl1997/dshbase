import repos from './repos.js';

// Batch GitHub GraphQL queries (40 repos each) to fetch live stars/forks/issues
// for every cataloged plugin. repos.json is generated from src/data/plugins.json.
export async function onRequest(context) {
  const token = context.env.GITHUB_TOKEN;
  const headers = { 'User-Agent': 'dshbase-stats', 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;

  const BATCH = 40;
  const out = {};
  const batches = [];
  for (let i = 0; i < repos.length; i += BATCH) {
    batches.push(repos.slice(i, i + BATCH));
  }

  await Promise.all(
    batches.map(async (batch, bi) => {
      const aliases = batch
        .map((r, j) => `r${bi}_${j}: repository(owner: "${r.owner}", name: "${r.repo}") { stargazerCount forkCount openIssues: issues(states: OPEN) { totalCount } }`)
        .join(' ');
      const query = `{ ${aliases} }`;
      try {
        const resp = await fetch('https://api.github.com/graphql', {
          method: 'POST',
          headers,
          body: JSON.stringify({ query }),
        });
        if (!resp.ok) return;
        const d = await resp.json();
        const data = d.data || {};
        batch.forEach((r, j) => {
          const v = data[`r${bi}_${j}`];
          if (v) out[r.slug || r.name] = { stars: v.stargazerCount || 0, forks: v.forkCount || 0, issues: (v.openIssues && v.openIssues.totalCount) || 0 };
        });
      } catch (e) {}
    })
  );

  return new Response(JSON.stringify(out), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' },
  });
}
