/**
 * Plugin `test` status helpers.
 *
 *   verified — dshbase actually ran an install test (L1+; compat-check / verify-runtime / L4).
 *   listed   — taken from npm / GitHub / dsh.so metadata; dshbase has NOT install-tested it.
 *   pending  — legacy "unverified" (queued, or a verify run failed — see `note`).
 *
 * Unknown / missing values are treated as `listed` (never as verified).
 */
export function pluginStatus(p) {
  const t = p && p.test;
  if (t === 'verified' || t === 'pending' || t === 'listed') return t;
  return 'listed';
}

export const isVerified = (p) => pluginStatus(p) === 'verified';

/** Untested = listed, or legacy pending with no test record at all. */
export function isUntested(p) {
  const s = pluginStatus(p);
  if (s === 'listed') return true;
  return s === 'pending' && !p.testDate && !(p.note || '').trim();
}

/**
 * dsh version from a real (passing) test result recorded in data (note text such as
 * "Headless L3 PASS on dsh 0.1.0-rc.8" or "验证: ok (0.1.0-rc.6)"), or a
 * peer/engines declaration if the row carries one. Returns '' when unknown.
 */
export function dshVersionFor(p) {
  if (!p) return '';
  const decl = p.dshPeer || p.peerDsh || (p.engines && (p.engines.dsh || p.engines['deepseek-harness'])) || '';
  if (decl) return String(decl);
  // Only a passing test result counts (a failure note is not a compatibility claim).
  if (pluginStatus(p) !== 'verified') return '';
  const n = String(p.note || '');
  const m = n.match(/(?:pass|verified|通过|\bok\b)[^.;；]*?\bdsh\s+v?(\d+\.\d+\.\d+(?:-[a-z]+\.\d+)?)/i)
    || n.match(/验证:\s*ok\s*\((\d+\.\d+\.\d+(?:-[a-z]+\.\d+)?)\)/i);
  return m ? m[1] : '';
}
