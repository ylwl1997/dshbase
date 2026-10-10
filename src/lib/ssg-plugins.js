import plugins from '../data/plugins.json';
import indexable from '../data/indexable-plugins.json';

const enSet = new Set(indexable.en || []);
const zhSet = new Set(indexable.zh || []);
/** New bulk ingest date — legacy catalog always gets static pages. */
export const BULK_ADDED = '2026-10-10';

export function shouldSsgEn(p) {
  const slug = p.slug ?? p.name;
  const stars = Number(p.stars) || 0;
  const added = p.added || '';
  return stars >= 10 || enSet.has(slug) || added < BULK_ADDED;
}

export function shouldSsgZh(p) {
  const slug = p.slug ?? p.name;
  const added = p.added || '';
  const hasZh = Boolean((p.desc_zh || '').trim());
  return zhSet.has(slug) || (added < BULK_ADDED && hasZh);
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
