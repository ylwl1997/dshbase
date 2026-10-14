/**
 * Cloudflare Email Address Obfuscation rewrites addresses into
 * /cdn-cgi/l/email-protection links. Ahrefs (and similar crawlers) follow
 * those as URLs and get 404s. The documented escape is HTML comment markers:
 *   <!--email_off-->…<!--/email_off-->
 * @see https://developers.cloudflare.com/waf/tools/scrape-shield/email-address-obfuscation/
 */

const EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;

export function looksLikeEmail(text) {
  return EMAIL_RE.test(String(text || ''));
}

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Wrap a block of HTML so CF leaves emails/mailto inside alone. */
export function withCfEmailOff(html) {
  if (!html) return '';
  if (html.includes('<!--email_off-->')) return html;
  return `<!--email_off-->${html}<!--/email_off-->`;
}

/**
 * Escape plain text for HTML. If it contains an email-like token, wrap with
 * email_off so Cloudflare does not inject /cdn-cgi/l/email-protection links.
 */
export function cfSafeTextHtml(text) {
  const escaped = escapeHtml(text || '');
  if (!escaped) return '';
  return looksLikeEmail(text) ? withCfEmailOff(escaped) : escaped;
}

/**
 * Build a CF-exempt mailto anchor (safe for set:html).
 * @param {string} address
 * @param {string} [label]
 */
export function mailtoHtml(address, label = address) {
  const href = `mailto:${address}`;
  return withCfEmailOff(`<a href="${escapeHtml(href)}">${escapeHtml(label)}</a>`);
}
