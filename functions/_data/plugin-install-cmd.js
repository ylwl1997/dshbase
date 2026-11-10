/**
 * Install commands for one catalog plugin.
 *
 * Lives in functions/_data/ so the Pages Function bundle includes it.
 * functions/plugins/[slug].js and functions/zh/plugins/[slug].js render
 * through functions/_data/render-plugin.js, which imports this file as a
 * sibling. Cloudflare Pages bundles modules reached from functions/; a
 * functions/ → src/ import is outside that graph. Astro pages, cards,
 * search, packs, and the install-cmd tests import this same file. One copy.
 *
 * Official pair: when both `installPreferred` and `installManual` are
 * non-empty, those strings are the commands.
 *   - Detail pages (en/zh Astro and functions/_data/render-plugin.js) show
 *     preferred first, then the manual equivalent. They do not show the
 *     default Web profile / Headless profile blocks.
 *   - Single-command surfaces (card copy, directory, search index, packs,
 *     scripts/gen-catalog.py) copy `installManual` only. The npm -g line
 *     stays on the detail page.
 *
 * Without that pair, each surface keeps its previous default so no other
 * plugin's command changes. scripts/gen-catalog.py mirrors catalogInstall().
 */

export const INSTALL_LABELS = {
  en: {
    preferred: 'Preferred (official README):',
    manual: 'Manual equivalent:',
    web: 'Web profile:',
    headless: 'Headless (CLI) profile:',
  },
  zh: {
    preferred: '首选（官方 README）：',
    manual: '手动等价：',
    web: 'Web profile：',
    headless: 'Headless（CLI）profile：',
  },
};

function text(value) {
  return typeof value === 'string' ? value.trim() : '';
}

/** Card, directory, search, and detail github: path. Does not strip a trailing slash. */
function siteGithub(url) {
  return String(url || '').replace('https://github.com/', '');
}

/** gen-catalog.py owner_repo(): drop the https prefix and trailing slashes. */
function catalogGithub(url) {
  return String(url || '').replace('https://github.com/', '').replace(/\/+$/, '');
}

/** functions/_data/render-plugin.js historical repo strip (http or https). */
function functionGithub(url) {
  return String(url || '').replace(/^https?:\/\/github\.com\//, '');
}

export function hasOfficialInstall(plugin) {
  return !!(text(plugin?.installPreferred) && text(plugin?.installManual));
}

/**
 * @param {object | null | undefined} plugin
 */
export function pluginInstall(plugin) {
  const p = plugin || {};
  const preferred = text(p.installPreferred);
  const manual = text(p.installManual);
  const official = !!(preferred && manual);
  const pkg = typeof p.pkg === 'string' ? p.pkg : '';
  const installPkg = typeof p.installPkg === 'string' ? p.installPkg : '';
  const npmWithPkg = !!(p.npm && pkg);
  const siteRepo = siteGithub(p.url);
  const catalogRepo = catalogGithub(p.url);
  const fnRepo = functionGithub(p.url);

  const web = npmWithPkg
    ? `dsh plugin --profile web add ${installPkg || pkg}`
    : `dsh plugin --profile web add github:${siteRepo}`;
  const headless = npmWithPkg
    ? `dsh plugin --profile headless add ${pkg}`
    : `dsh plugin --profile headless add github:${siteRepo}`;
  const single = npmWithPkg
    ? `dsh plugin add ${pkg}`
    : `dsh plugin add github:${siteRepo}`;
  const catalog = installPkg
    ? `dsh plugin --profile web add ${installPkg}`
    : npmWithPkg
      ? `dsh plugin add ${pkg}`
      : `dsh plugin add github:${catalogRepo}`;
  const spec = installPkg || pkg;
  const functionWeb = p.npm && spec
    ? `dsh plugin --profile web add ${spec}`
    : `dsh plugin --profile web add github:${fnRepo}`;

  if (official) {
    return {
      official: true,
      preferred,
      manual,
      single: manual,
      catalog: manual,
      web: '',
      headless: '',
      functionWeb: '',
    };
  }
  return {
    official: false,
    preferred: '',
    manual: '',
    single,
    catalog,
    web,
    headless,
    functionWeb,
  };
}

export function singleInstallCommand(plugin) {
  return pluginInstall(plugin).single;
}

export function catalogInstall(plugin) {
  return pluginInstall(plugin).catalog;
}

/** Meta-description phrase. Official plugins use the manual command; others stay as written today. */
export function metaInstallPhrase(plugin, locale) {
  const ins = pluginInstall(plugin);
  if (ins.official) return ins.single;
  if (plugin?.npm) return `dsh plugin add ${plugin.pkg}`;
  return locale === 'zh' ? 'npm 源码' : 'npm source';
}

function labelsFor(locale) {
  return locale === 'zh' ? INSTALL_LABELS.zh : INSTALL_LABELS.en;
}

/** Detail-page command blocks for the Astro en/zh plugin pages. */
export function astroDetailBlocks(plugin, locale) {
  const ins = pluginInstall(plugin);
  const labels = labelsFor(locale);
  if (ins.official) {
    return [
      { label: labels.preferred, command: ins.preferred },
      { label: labels.manual, command: ins.manual },
    ];
  }
  return [
    { label: labels.web, command: ins.web },
    { label: labels.headless, command: ins.headless },
  ];
}

/**
 * Detail-page command blocks for functions/_data/render-plugin.js.
 * Non-official pages keep the single "Web profile" / "Web 配置" line.
 */
export function functionDetailBlocks(plugin, locale) {
  const ins = pluginInstall(plugin);
  if (ins.official) {
    const labels = labelsFor(locale);
    return [
      { label: labels.preferred, command: ins.preferred },
      { label: labels.manual, command: ins.manual },
    ];
  }
  const label = locale === 'zh' ? 'Web 配置：' : 'Web profile:';
  return [{ label, command: ins.functionWeb }];
}
