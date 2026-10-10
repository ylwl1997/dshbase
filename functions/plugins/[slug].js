import fallback from '../_data/plugin-fallback.js';
import { renderPluginPage } from '../_data/render-plugin.js';

export async function onRequestGet(context) {
  const slug = context.params.slug;
  const p = fallback[slug];
  if (!p) return new Response('Not found', { status: 404 });
  // If EN was statically generated, CF serves the file first — this only runs for gaps.
  return renderPluginPage(p, 'en');
}
