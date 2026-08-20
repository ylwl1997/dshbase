/** Classify pending plugins by note text for the audit failure browser. */
export function classifyFailNote(note) {
  const n = (note || '').toLowerCase();
  if (!n) return 'untested';
  if (n.includes('install-fail') || n.includes('install fail') || n.includes('err_pnpm') || n.includes('404')) return 'install-fail';
  if (n.includes('load-fail') || n.includes('load fail') || n.includes('dump-config') || n.includes('boot')) return 'load-fail';
  if (n.includes('webonly') || n.includes('web l3') || n.includes('cdp')) return 'webonly';
  if (n.includes('runtime-fail') || n.includes('runtime fail') || n.includes('l3')) return 'runtime-fail';
  if (n.includes('external') || n.includes('needs ') || n.includes('account') || n.includes('api key')) return 'external-deps';
  return 'other';
}

export function pendingFailRows(plugins) {
  const all = Object.entries(plugins).flatMap(([cat, items]) =>
    items.map((p) => ({ ...p, cat }))
  );
  return all
    .filter((p) => p.test === 'pending')
    .map((p) => ({
      name: p.name,
      slug: p.slug || p.name,
      cat: p.cat,
      note: p.note || '',
      testDate: p.testDate || '',
      webonly: !!p.webonly,
      stars: p.stars ?? 0,
      failClass: p.webonly ? 'webonly' : classifyFailNote(p.note),
    }))
    .sort((a, b) => (b.stars || 0) - (a.stars || 0));
}

export const FAIL_LABELS_EN = {
  'install-fail': 'Install fail',
  'load-fail': 'Load fail',
  'runtime-fail': 'Runtime fail',
  webonly: 'Web-only / CDP',
  'external-deps': 'External deps',
  untested: 'Not yet tested',
  other: 'Other / note',
};

export const FAIL_LABELS_ZH = {
  'install-fail': '安装失败',
  'load-fail': '加载失败',
  'runtime-fail': '运行失败',
  webonly: '仅 Web / CDP',
  'external-deps': '需外部依赖',
  untested: '尚未实测',
  other: '其他 / 备注',
};
