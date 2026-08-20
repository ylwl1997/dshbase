/** Classify pending plugins by note text for the audit failure browser.
 *
 * Important: old notes like "web L3 runtime-fail … (CDP E2E)" are *not*
 * "awaiting L4". They failed a prior web/CDP batch and should show as the
 * concrete fail type. True L4 queue is webonly + "待 L4" (or L4 fail).
 */

function hasFailToken(n, kind) {
  return (
    n.includes(`${kind}-fail`) ||
    n.includes(`${kind} fail`) ||
    (kind === 'install' && (n.includes('err_pnpm') || n.includes('404'))) ||
    (kind === 'load' && (n.includes('dump-config') || n.includes('boot')))
  );
}

/** @param {string} note @param {{ webonly?: boolean }} [opts] */
export function classifyFailNote(note, opts = {}) {
  const n = (note || '').toLowerCase();
  const webonly = !!opts.webonly;

  if (!n) return webonly ? 'awaiting-l4' : 'untested';

  // L4 CDP outcomes (after L3 web-only) — check before generic "cdp"/"web l3".
  if (/\bl4\b/.test(n) && hasFailToken(n, 'runtime')) return 'l4-fail';
  if (/\bl4\b/.test(n) && hasFailToken(n, 'load')) return 'l4-fail';
  if (/\bl4\b/.test(n) && hasFailToken(n, 'install')) return 'l4-fail';
  if (n.includes('l4 web cdp') && (n.includes('fail') || n.includes('still web-only'))) {
    return 'l4-fail';
  }

  // True queue: L3 said web-only, waiting for first/retry L4 (not yet failed L4).
  if (
    webonly &&
    (n.includes('待 l4') ||
      n.includes('待 web') ||
      n.includes('web-only') ||
      n.includes('webonly')) &&
    !hasFailToken(n, 'runtime') &&
    !hasFailToken(n, 'load') &&
    !hasFailToken(n, 'install')
  ) {
    return 'awaiting-l4';
  }
  if (webonly && (n.includes('待 l4') || /^验证:\s*web-only/.test(n.trim()))) {
    // "验证: web-only；L4 … fail" already handled above; leftover awaiting.
    if (!/\bl4\b.*fail/.test(n)) return 'awaiting-l4';
  }

  // Concrete fails (headless L3 or old "web L3 … CDP E2E" backlog).
  if (hasFailToken(n, 'install')) return 'install-fail';
  if (hasFailToken(n, 'load')) return 'load-fail';
  if (hasFailToken(n, 'runtime') || (n.includes('l3') && n.includes('fail'))) {
    return 'runtime-fail';
  }

  if (n.includes('external') || n.includes('needs ') || n.includes('account') || n.includes('api key')) {
    return 'external-deps';
  }

  // webonly flag with no fail token → still waiting on L4
  if (webonly) return 'awaiting-l4';

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
      failClass: classifyFailNote(p.note, { webonly: !!p.webonly }),
    }))
    .sort((a, b) => (b.stars || 0) - (a.stars || 0));
}

export const FAIL_LABELS_EN = {
  'install-fail': 'Install fail',
  'load-fail': 'Load fail',
  'runtime-fail': 'Runtime fail',
  'awaiting-l4': 'Awaiting L4',
  'l4-fail': 'L4 failed',
  'external-deps': 'External deps',
  untested: 'Not yet tested',
  other: 'Other / note',
  // legacy key kept so old bookmarks/filters degrade gracefully
  webonly: 'Web-only / CDP',
};

export const FAIL_LABELS_ZH = {
  'install-fail': '安装失败',
  'load-fail': '加载失败',
  'runtime-fail': '运行失败',
  'awaiting-l4': '待 L4 CDP',
  'l4-fail': 'L4 未通过',
  'external-deps': '需外部依赖',
  untested: '尚未实测',
  other: '其他 / 备注',
  webonly: '仅 Web / CDP',
};

/** Chip order on audit pages */
export const FAIL_ORDER = [
  'install-fail',
  'load-fail',
  'runtime-fail',
  'awaiting-l4',
  'l4-fail',
  'external-deps',
  'other',
  'untested',
];
