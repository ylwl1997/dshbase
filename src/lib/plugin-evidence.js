/**
 * Short evidence for plugin detail pages (我们的评价 / Our take, 实测报告 / Test report).
 *
 * Data file: src/data/plugin-evidence.json
 *   { "plugins": { "<slug>": Evidence } }
 * Schema: src/data/plugin-evidence.schema.json
 *
 * A follow-up verification PR fills plugins[slug]. This module does not read
 * catalog `test`, stars, `note`, `webonly`, or `needs`, and it does not invent
 * a Verified badge. Missing or invalid records render as an honest empty report.
 *
 * Evidence fields:
 *   conclusion, conclusion_zh          short sentences, both locales
 *   dshVersionRequested                `@deepseek-ai/dsh@latest` (pilot value `latest` is accepted)
 *   dshVersionActual                   first line of `dsh --version` after that tag resolved
 *   testDate                           YYYY-MM-DD
 *   needs, needs_zh                    optional external accounts/services
 *   levels.L1..L4                      { status, reason, reason_zh }
 *     status: pass | skip | fail | needs
 *     web-only (GUI service, no headless pass) is skip, never pass or fail
 *     a missing external account/service is needs, never pass or fail
 *   conclusion / conclusion_zh must not contain the word Verified or 「已验证」.
 *     A passing L3, or a skipped L4 on a theme/Web plugin, is layer evidence
 *     only. The validator rejects badge wording; pages do not rewrite it.
 *
 * Filled presentation (same record, two modules):
 *   review  conclusion, needs when present, disclaimer
 *   report  dist-tag, dsh --version, test date, L1–L4, needs
 */

export const REQUESTED_DIST_TAG = '@deepseek-ai/dsh@latest';
export const LEVELS = ['L1', 'L2', 'L3', 'L4'];
export const STATUSES = ['pass', 'skip', 'fail', 'needs'];

const REQUESTED_OK = new Set([REQUESTED_DIST_TAG, 'latest']);
const SEMVER = /\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?/;

const COPY = {
  zh: {
    noHeadline: '尚无短证据报告',
    noBody: '这里还没有可核对的逐级实测记录。Star 数、目录 test 字段、web-only 标记，以及插件是否需要外部账号或服务，都不会在这里被写成通过或失败。目录徽章仍按 catalog 原样显示。',
    archived: 'GitHub 仓库在目录中为已归档。这只是仓库状态，不是实测结论。',
    requestedLabel: '请求的发行标签',
    requestedNote: '不是写死的 rc',
    actualLabel: '实测时 dsh --version',
    dateLabel: '测试日期',
    needsLabel: '需要的外部账号 / 服务',
    disclaimer: '以上是这次实测写下的证据，不改写目录徽章。跳过（含 web-only）和需外部条件不是通过，也不是失败。',
    status: { pass: '通过', skip: '跳过', fail: '未通过', needs: '需外部条件' },
    levelName: {
      L1: 'L1 安装',
      L2: 'L2 加载',
      L3: 'L3 Headless',
      L4: 'L4 Web CDP',
    },
  },
  en: {
    noHeadline: 'No short evidence report',
    noBody: 'There is no checkable per-level test record on this page. Stars, the catalog test field, a web-only flag, and whether the plugin needs an external account or service are not shown here as a pass or a failure. The catalog badge stays as published.',
    archived: 'The GitHub repository is marked archived in the catalog. That is a repository fact, not a test result.',
    requestedLabel: 'Requested dist-tag',
    requestedNote: 'not a frozen rc',
    actualLabel: 'dsh --version at test time',
    dateLabel: 'Test date',
    needsLabel: 'External accounts / services required',
    disclaimer: 'This is the evidence written for that run. It does not change the catalog badge. Skip (including web-only) and needs are not a pass and not a failure.',
    status: { pass: 'Pass', skip: 'Skip', fail: 'Fail', needs: 'Needs' },
    levelName: {
      L1: 'L1 Install',
      L2: 'L2 Load',
      L3: 'L3 Headless',
      L4: 'L4 Web CDP',
    },
  },
};

function text(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function looksLikeRawLog(value) {
  const s = String(value || '');
  if (/\n\s*at \S/.test(s) || /^\s*at \S+\s+\(/m.test(s)) return true;
  const lines = s.split(/\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length >= 4) return true;
  return false;
}

/** Badge words. English matches the word Verified in any case. Chinese matches 已验证 exactly. */
export function claimsVerifiedBadge(value) {
  const s = text(value);
  return /\bverified\b/i.test(s) || s.includes('已验证');
}

function isHumanText(value, { min = 8, max = 400 } = {}) {
  const s = text(value);
  if (s.length < min || s.length > max) return false;
  if (looksLikeRawLog(s)) return false;
  if (!/[\p{L}]/u.test(s)) return false;
  if (!/[\s\u3400-\u9fff]/.test(s)) return false;
  return true;
}

function isIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function isResolvedVersion(value) {
  const s = text(value);
  if (!s || s.length > 80 || /[\r\n]/.test(s)) return false;
  if (/@latest\b/i.test(s)) return false;
  if (/^@deepseek-ai\/dsh@/i.test(s)) return false;
  if (s === 'latest') return false;
  return SEMVER.test(s);
}

function blob(reason, reasonZh) {
  return `${reason} ${reasonZh}`.toLowerCase();
}

function isWebOnlyExplanation(reason, reasonZh) {
  const hay = blob(reason, reasonZh);
  if (!/web-?only|webonly|仅\s*web|waiting for service/.test(hay)) return false;
  if (/did not mount|not in the page|未出现|没有挂载|boot error|崩溃|crash|timeout|超时|exception|异常/.test(hay)) {
    return false;
  }
  return true;
}

function isNeedsExplanation(reason, reasonZh) {
  const hay = blob(reason, reasonZh);
  if (!/needs-env|external account|外部账号|api key|credential|扫码/.test(hay)) return false;
  if (/崩溃|crash|timeout|超时|exception|异常|did not mount|未出现|没有挂载/.test(hay)) return false;
  return /not set|missing|未设置|没有配置|没有提供|无法提供|需要|requires|\bneeds\b/.test(hay);
}

/**
 * @param {object} entry
 * @returns {{ ok: true, value: object } | { ok: false, error: string }}
 */
export function validateEvidence(entry) {
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
    return { ok: false, error: 'record is not an object' };
  }
  const conclusion = text(entry.conclusion);
  const conclusionZh = text(entry.conclusion_zh);
  if (!isHumanText(conclusion, { max: 320 })) {
    return { ok: false, error: 'conclusion must be a short human sentence' };
  }
  if (!isHumanText(conclusionZh, { max: 320 })) {
    return { ok: false, error: 'conclusion_zh must be a short human sentence' };
  }
  if (claimsVerifiedBadge(conclusion)) {
    return { ok: false, error: 'conclusion must not claim Verified or 已验证' };
  }
  if (claimsVerifiedBadge(conclusionZh)) {
    return { ok: false, error: 'conclusion_zh must not claim Verified or 已验证' };
  }
  const requested = text(entry.dshVersionRequested);
  if (!REQUESTED_OK.has(requested)) {
    return { ok: false, error: `dshVersionRequested must be ${REQUESTED_DIST_TAG} (or latest), never a frozen rc` };
  }
  const actual = text(entry.dshVersionActual);
  if (!isResolvedVersion(actual)) {
    return { ok: false, error: 'dshVersionActual must be the one-line output of dsh --version' };
  }
  const testDate = text(entry.testDate);
  if (!isIsoDate(testDate)) {
    return { ok: false, error: 'testDate must be YYYY-MM-DD' };
  }
  const levelsIn = entry.levels;
  if (!levelsIn || typeof levelsIn !== 'object' || Array.isArray(levelsIn)) {
    return { ok: false, error: 'levels must be an object with L1, L2, L3, and L4' };
  }
  const levels = {};
  let needsLevel = false;
  for (const id of LEVELS) {
    const row = levelsIn[id];
    if (!row || typeof row !== 'object') return { ok: false, error: `${id} is missing` };
    const status = text(row.status);
    if (!STATUSES.includes(status)) {
      return { ok: false, error: `${id}.status must be pass, skip, fail, or needs` };
    }
    const reason = text(row.reason);
    const reasonZh = text(row.reason_zh);
    if (!isHumanText(reason)) return { ok: false, error: `${id}.reason must be a short human sentence, not a raw log` };
    if (!isHumanText(reasonZh)) return { ok: false, error: `${id}.reason_zh must be a short human sentence, not a raw log` };
    if ((status === 'pass' || status === 'fail') && isWebOnlyExplanation(reason, reasonZh)) {
      return { ok: false, error: `${id} treats web-only as ${status}; use skip` };
    }
    if ((status === 'pass' || status === 'fail') && isNeedsExplanation(reason, reasonZh)) {
      return { ok: false, error: `${id} treats an external account or service as ${status}; use needs` };
    }
    if (status === 'needs') needsLevel = true;
    levels[id] = { status, reason, reason_zh: reasonZh };
  }
  const needs = text(entry.needs);
  const needsZh = text(entry.needs_zh);
  if (needs || needsZh || needsLevel) {
    if (!isHumanText(needs)) return { ok: false, error: 'needs must describe the external account or service' };
    if (!isHumanText(needsZh)) return { ok: false, error: 'needs_zh must describe the external account or service' };
  }
  return {
    ok: true,
    value: {
      conclusion,
      conclusion_zh: conclusionZh,
      dshVersionRequested: REQUESTED_DIST_TAG,
      dshVersionActual: actual,
      testDate,
      needs,
      needs_zh: needsZh,
      levels,
    },
  };
}

export function evidenceEntries(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return {};
  const source = data.plugins && typeof data.plugins === 'object' && !Array.isArray(data.plugins)
    ? data.plugins
    : data;
  const out = {};
  for (const [key, value] of Object.entries(source)) {
    if (key === 'plugins' || key.startsWith('$') || key.startsWith('_')) continue;
    if (value && typeof value === 'object' && !Array.isArray(value)) out[key] = value;
  }
  return out;
}

/**
 * Which parts of one evidence record each filled module shows.
 * Empty pages ignore this and keep the shared “no short evidence report” copy.
 */
export function filledSections(variant) {
  const report = variant === 'report';
  return {
    conclusion: !report,
    meta: report,
    levels: report,
    needs: true,
    disclaimer: !report,
  };
}

function emptyView(locale, archived) {
  const copy = COPY[locale] || COPY.en;
  return {
    hasEvidence: false,
    headline: copy.noHeadline,
    body: copy.noBody,
    archivedNote: archived ? copy.archived : '',
    dshVersionRequested: '',
    dshVersionActual: '',
    testDate: '',
    requestedLabel: '',
    requestedNote: '',
    actualLabel: '',
    dateLabel: '',
    needsLabel: '',
    needs: '',
    levels: [],
    disclaimer: '',
  };
}

/**
 * View model for one plugin page. Does not consult catalog test, stars, or notes.
 * @param {string} slug
 * @param {{ locale?: string, archived?: boolean, data?: object }} [opts]
 */
export function presentEvidence(slug, opts = {}) {
  const locale = opts.locale === 'zh' ? 'zh' : 'en';
  const copy = COPY[locale];
  const entries = evidenceEntries(opts.data);
  const raw = entries[slug];
  if (!raw) return emptyView(locale, !!opts.archived);
  const validated = validateEvidence(raw);
  if (!validated.ok) {
    console.warn(`[plugin-evidence] ${slug}: ${validated.error}`);
    return emptyView(locale, !!opts.archived);
  }
  const value = validated.value;
  return {
    hasEvidence: true,
    headline: locale === 'zh' ? value.conclusion_zh : value.conclusion,
    body: '',
    archivedNote: opts.archived ? copy.archived : '',
    dshVersionRequested: value.dshVersionRequested,
    dshVersionActual: value.dshVersionActual,
    testDate: value.testDate,
    requestedLabel: copy.requestedLabel,
    requestedNote: copy.requestedNote,
    actualLabel: copy.actualLabel,
    dateLabel: copy.dateLabel,
    needsLabel: copy.needsLabel,
    needs: locale === 'zh' ? value.needs_zh : value.needs,
    levels: LEVELS.map((id) => {
      const row = value.levels[id];
      return {
        id,
        name: copy.levelName[id],
        status: row.status,
        statusLabel: copy.status[row.status],
        reason: locale === 'zh' ? row.reason_zh : row.reason,
      };
    }),
    disclaimer: copy.disclaimer,
  };
}
