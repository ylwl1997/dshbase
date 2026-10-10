import fallback from '../../_data/plugin-fallback.js';
import { renderPluginPage } from '../../_data/render-plugin.js';

export async function onRequestGet(context) {
  const slug = context.params.slug;
  const p = fallback[slug];
  if (!p) return new Response('Not found', { status: 404 });
  return renderPluginPage(p, 'zh');
}
