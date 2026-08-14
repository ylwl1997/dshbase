export async function onRequest(context) {
  try {
    const out = { status: 'ok', time: Date.now() };
    return new Response(JSON.stringify(out), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  } catch (e) {
    return new Response('error: ' + e.message, { status: 500 });
  }
}
