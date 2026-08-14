export async function onRequest(context) {
  try {
    const r = await fetch('https://api.github.com/repos/ylwl1997/dsh-browser');
    const d = await r.json();
    return new Response(JSON.stringify({ stars: d.stargazers_count }), { headers: { 'Content-Type': 'application/json' } });
  } catch (e) {
    return new Response('err: ' + String(e), { status: 500, headers: { 'Content-Type': 'text/plain' } });
  }
}
