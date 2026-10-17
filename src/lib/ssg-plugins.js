import plugins from '../data/plugins.json';
import indexable from '../data/indexable-plugins.json';

const enSet = new Set(indexable.en || []);
const zhSet = new Set(indexable.zh || []);
/** Legacy catalog always gets static pages; post-bulk only high-star / indexable / recent-verified. */
export const BULK_ADDED = '2026-10-10';

/** Recent curated rows: verified, or metadata-listed since #145 (keeps their static pages). */
function isRecentVerified(p) {
  return (p.test === 'verified' || p.test === 'listed') && (p.added || '') >= '2026-10-14';
}

export function shouldSsgEn(p) {
  const slug = p.slug ?? p.name;
  const stars = Number(p.stars) || 0;
  const added = p.added || '';
  return stars >= 10 || enSet.has(slug) || added < BULK_ADDED || isRecentVerified(p);
}

export function shouldSsgZh(p) {
  const slug = p.slug ?? p.name;
  const added = p.added || '';
  const hasZh = Boolean((p.desc_zh || '').trim());
  return zhSet.has(slug) || (added < BULK_ADDED && hasZh) || isRecentVerified(p);
}

export function enStaticPaths() {
  return Object.entries(plugins).flatMap(([cat, items]) =>
    items.filter(shouldSsgEn).map((p) => ({ params: { slug: p.slug ?? p.name }, props: { cat, p } })),
  );
}

export function zhStaticPaths() {
  return Object.entries(plugins).flatMap(([cat, items]) =>
    items.filter(shouldSsgZh).map((p) => ({ params: { slug: p.slug ?? p.name }, props: { cat, p } })),
  );
}
