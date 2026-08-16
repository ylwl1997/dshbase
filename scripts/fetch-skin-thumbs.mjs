// fetch-skin-thumbs.mjs
// Download real skin preview thumbnails (320x200 WebP) from the source repo
// whyihaveyou/dsh-themes and sync thumb/tags/bodyAttr fields into skins.json.
//
// Usage: node scripts/fetch-skin-thumbs.mjs
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const RAW = 'https://raw.githubusercontent.com/whyihaveyou/dsh-themes/HEAD/packages/skin-center/assets';
const THUMB_DIR = join(ROOT, 'public', 'skins', 'thumbs');
const SKINS_JSON = join(ROOT, 'src', 'data', 'skins.json');

const CONCURRENCY = 12;

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return res.json();
}

async function download(url, dest, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status}`);
      const buf = Buffer.from(await res.arrayBuffer());
      if (buf.length < 200) throw new Error(`too small (${buf.length})`);
      writeFileSync(dest, buf);
      return true;
    } catch (e) {
      if (i === retries - 1) { console.error(`FAIL ${url}: ${e.message}`); return false; }
      await new Promise((r) => setTimeout(r, 500 * (i + 1)));
    }
  }
}

async function main() {
  mkdirSync(THUMB_DIR, { recursive: true });

  const manifest = await fetchJson(`${RAW}/manifest.json`);
  const local = JSON.parse(readFileSync(SKINS_JSON, 'utf8'));

  // id -> source entry
  const src = new Map(manifest.skins.map((s) => [s.id, s]));

  let matched = 0, missing = 0, downloaded = 0, failed = 0;
  const jobs = [];

  for (const skin of local.skins) {
    const s = src.get(skin.id);
    if (!s || !s.thumb) { missing++; console.warn(`no source entry for ${skin.id}`); continue; }
    matched++;
    skin.thumb = { light: s.thumb.light, dark: s.thumb.dark };
    if (s.bodyAttr) skin.bodyAttr = s.bodyAttr;
    if (Array.isArray(s.tags) && s.tags.length) skin.tags = s.tags;
    if (s.collection) skin.collection = s.collection;
    for (const kind of ['light', 'dark']) {
      const fname = skin.thumb[kind].split('/').pop();
      const dest = join(THUMB_DIR, fname);
      if (existsSync(dest)) { downloaded++; continue; }
      jobs.push({ url: `${RAW}/${skin.thumb[kind]}`, dest, id: skin.id, kind });
    }
  }

  // Download with limited concurrency
  let cursor = 0;
  async function worker() {
    while (cursor < jobs.length) {
      const j = jobs[cursor++];
      if (await download(j.url, j.dest)) downloaded++; else failed++;
      if ((downloaded + failed) % 40 === 0) console.log(`  ... ${downloaded} ok, ${failed} failed`);
    }
  }
  const workers = Array.from({ length: CONCURRENCY }, worker);
  await Promise.all(workers);

  writeFileSync(SKINS_JSON, JSON.stringify(local, null, 1) + '\n', 'utf8');
  console.log(`\nmatched=${matched} missing=${missing} downloaded(ok+existing)=${downloaded} failed=${failed}`);
  console.log(`wrote ${SKINS_JSON}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
