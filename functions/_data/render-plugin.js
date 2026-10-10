function esc(s) {
  return String(s || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function renderPluginPage(p, lang) {
  const zh = lang === 'zh';
  const title = zh ? `${esc(p.name)} — 已验证插件 | dshbase` : `${esc(p.name)} — Verified plugin | dshbase`;
  const desc = zh ? (p.desc_zh || p.desc || p.name) : (p.desc || p.name);
  const status = zh ? '已验证' : 'Verified';
  const dir = zh ? '/zh/plugins/directory/' : '/plugins/directory/';
  const other = zh ? `/plugins/${encodeURIComponent(p.slug)}/` : `/zh/plugins/${encodeURIComponent(p.slug)}/`;
  const otherLab = zh ? 'EN' : '中文';
  const repo = (p.url || '').replace(/^https?:\/\/github\.com\//, '');
  const install = p.npm && p.pkg
    ? `dsh plugin --profile web add ${p.pkg}`
    : `dsh plugin --profile web add github:${repo}`;
  const html = `<!doctype html>
<html lang="${zh ? 'zh-CN' : 'en'}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<meta name="description" content="${esc(desc)}">
<meta name="googlebot" content="noindex, follow">
<link rel="canonical" href="https://dshbase.com${zh ? '/zh' : ''}/plugins/${esc(p.slug)}/">
<style>
body{margin:0;font:15px/1.55 system-ui,sans-serif;background:#0b1020;color:#e6eaf2}
a{color:#818cf8} .wrap{max-width:820px;margin:0 auto;padding:28px 18px}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;background:#14532d;color:#86efac;font-size:12px;font-weight:600}
pre{background:#121a2e;border:1px solid #243049;border-radius:10px;padding:12px 14px;overflow:auto}
.muted{color:#8792a8;font-size:13px}
.top{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:18px}
</style>
</head>
<body>
<main class="wrap">
  <div class="top">
    <a href="${dir}">${zh ? '插件目录' : 'Plugin directory'}</a>
    <a href="${other}">${otherLab}</a>
  </div>
  <h1>${esc(p.name)}</h1>
  <p><span class="badge">${status}</span>
    ${p.stars ? ` · ★${p.stars}` : ''}
    ${p.cat ? ` · ${esc(p.cat)}` : ''}</p>
  <p>${esc(desc)}</p>
  <h2>${zh ? '安装' : 'Install'}</h2>
  <pre><code>${esc(install)}</code></pre>
  ${p.url ? `<p><a href="${esc(p.url)}" rel="noopener" target="_blank">${zh ? '在 GitHub 查看' : 'View on GitHub'} ↗</a></p>` : ''}
  <p class="muted">${zh ? '本页为目录条目的轻量详情（按需生成）。' : 'Lightweight on-demand detail page for this directory entry.'}</p>
</main>
</body></html>`;
  return new Response(html, {
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=300',
    },
  });
}
