import fallback from '../../_data/plugin-fallback.js';
import { renderPluginPage } from '../../_data/render-plugin.js';

const RESERVED = new Set(['directory', 'compare']);

export async function onRequestGet(context) {
  const slug = context.params.slug;
  const { request, env } = context;

  if (RESERVED.has(slug)) {
    return env.ASSETS.fetch(request);
  }

  const asset = await env.ASSETS.fetch(request);
  if (asset.status !== 404) return asset;

  const p = fallback[slug];
  if (!p) return new Response('Not found', { status: 404 });
  return renderPluginPage(p, 'zh');
}
