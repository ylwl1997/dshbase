export async function onRequest(context) {
  const out = { status: 'ok' };
  return new Response(JSON.stringify(out), { headers: { 'Content-Type': 'application/json' } });
}
