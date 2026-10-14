/**
 * Plugin helpers.
 *
 * Historical note: googlebot noindex via indexable-plugins.json whitelist was
 * a regression for organic plugin-detail traffic. Plugin detail pages (EN+ZH)
 * are indexable again; keep whitelist data/scripts for analytics only.
 *
 * Soft-deleted plugin URLs that 301 via public/_redirects must not appear in
 * sitemaps (see scripts/gen-sitemap.py).
 */
import plugins from '../data/plugins.json';
import indexable from '../data/indexable-plugins.json';

const enSet = new Set(indexable.en);
const zhSet = new Set(indexable.zh);

/** @deprecated Whitelist kept for analytics; plugin pages no longer use this for robots. */
export function isPluginIndexable(slug, lang = 'en') {
  return lang === 'zh' ? zhSet.has(slug) : enSet.has(slug);
}

/** Demote README headings one level (h1→h2 … h5→h6) so the page keeps a single h1. */
export function demoteReadmeHeadings(html) {
  if (!html) return '';
  let out = html;
  for (let n = 5; n >= 1; n--) {
    const reOpen = new RegExp(`<h${n}(\\s|>)`, 'gi');
    const reClose = new RegExp(`</h${n}>`, 'gi');
    out = out.replace(reOpen, `<h${n + 1}$1`).replace(reClose, `</h${n + 1}>`);
  }
  return out;
}

export function allPluginsFlat() {
  return Object.entries(plugins).flatMap(([cat, items]) =>
    items.map((p) => ({ ...p, cat, slug: p.slug ?? p.name })),
  );
}

export const INDEXABLE_COUNTS = indexable.counts;
