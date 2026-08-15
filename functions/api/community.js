// Live official-repo community pulse: discussion count per category for
// deepseek-ai/deepseek-harness. Two GraphQL round-trips: (1) fetch categories,
// (2) count discussions per category by id. Falls back to {} on any failure —
// the dashboard renders its snapshot then.
export async function onRequest(context) {
  const token = context.env.GITHUB_TOKEN;
  const headers = { 'User-Agent': 'dshbase-community', 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const gql = async (query) => {
    const r = await fetch('https://api.github.com/graphql', { method: 'POST', headers, body: JSON.stringify({ query }) });
    if (!r.ok) return null;
    const d = await r.json();
    return d.data || null;
  };

  try {
    const repo = 'repository(owner: "deepseek-ai", name: "deepseek-harness")';
    const meta = await gql(`{ ${repo} { discussions { totalCount } discussionCategories(first: 10) { nodes { name id } } } }`);
    if (!meta || !meta.repository) return new Response('{}', json());
    const { totalCount } = meta.repository.discussions;
    const cats = meta.repository.discussionCategories.nodes;

    const aliases = cats.map((c, i) => `c${i}: discussions(categoryId: "${c.id}") { totalCount }`).join(' ');
    const counts = await gql(`{ ${repo} { ${aliases} } }`);
    const categories = {};
    if (counts && counts.repository) {
      cats.forEach((c, i) => {
        const v = counts.repository[`c${i}`];
        if (v) categories[c.name] = v.totalCount || 0;
      });
    }
    return new Response(JSON.stringify({ total: totalCount || 0, categories }), json());
  } catch (e) {
    return new Response('{}', json());
  }
}

function json() {
  return { headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' } };
}
