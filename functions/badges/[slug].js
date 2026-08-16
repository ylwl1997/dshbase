import data from './data.js';

// /badges/<name>.svg — shields-style SVG badge for embedding in a plugin's README.
// The badge links back to the plugin's dshbase page (the embed markdown is shown
// on each plugin detail page). Mirrors the "install-tested vs listed" distinction
// that is dshbase's core differentiator: we actually ran `dsh plugin add`.
const BLUE = '#4D6BFE';
const GREEN = '#1a7f37';
const GRAY = '#6b7280';

function box(text, fill, x) {
  // 7px per char + padding is a close-enough width estimate for the font.
  const w = Math.max(20, text.length * 7 + 14);
  return {
    x,
    w,
    textX: x + w / 2,
    text,
    fill,
  };
}

function badge(left, right, rightColor) {
  const L = box(left, BLUE, 0);
  const R = box(right, rightColor, L.w);
  const W = L.w + R.w;
  const H = 20;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" role="img" aria-label="${left}: ${right}">
  <title>${left}: ${right}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".25"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect width="${W}" height="${H}" rx="3" fill="#555"/>
  <rect x="${L.x}" width="${L.w}" height="${H}" fill="${L.fill}"/>
  <rect x="${R.x}" width="${R.w}" height="${H}" fill="${R.fill}"/>
  <rect width="${W}" height="${H}" rx="3" fill="url(#s)"/>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
    <text x="${L.textX}" y="14">${escapeXml(L.text)}</text>
    <text x="${R.textX}" y="14">${escapeXml(R.text)}</text>
  </g>
</svg>`;
}

function escapeXml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export async function onRequest(context) {
  const raw = decodeURIComponent(context.params.slug || '');
  const name = raw.replace(/\.svg$/, '');

  let svg;
  if (data[name] === 'verified') {
    svg = badge('dshbase', 'install-tested', GREEN);
  } else if (data[name] === 'pending') {
    svg = badge('dshbase', 'listed', GRAY);
  } else {
    svg = badge('dshbase', 'plugin', GRAY);
  }

  return new Response(svg, {
    headers: {
      'Content-Type': 'image/svg+xml; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=86400',
    },
  });
}
