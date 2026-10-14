import fallback from '../../_data/plugin-fallback.js';
import { renderPluginPage } from '../../_data/render-plugin.js';

const RESERVED = new Set(['directory', 'compare']);

async function assetsOrNext(env, request) {
  const url = new URL(request.url);
  const candidates = [request];
  if (url.pathname.endsWith('/')) {
    const u = new URL(url); u.pathname = u.pathname.replace(/\/$/, '') || '/';
    candidates.push(new Request(u, request));
  } else {
    const u = new URL(url); u.pathname = u.pathname + '/';
    candidates.push(new Request(u, request));
  }
  for (const req of candidates) {
    const res = await env.ASSETS.fetch(req);
    if (res.status !== 404) return res;
  }
  return null;
}

export async function onRequestGet(context) {
  const slug = context.params.slug;
  const { request, env } = context;

  if (RESERVED.has(slug)) {
    const asset = await assetsOrNext(env, request);
    if (asset) return asset;
    return Response.redirect(new URL('/zh/plugins/directory/', request.url), 302);
  }

  const asset = await assetsOrNext(env, request);
  if (asset) return asset;

  const p = fallback[slug];
  if (!p) {
    return Response.redirect(new URL('/zh/plugins/directory/', request.url), 302);
  }
  return renderPluginPage(p, 'zh');
}
