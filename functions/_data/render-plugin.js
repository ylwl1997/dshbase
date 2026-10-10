function esc(s) {
  return String(s || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** Lightweight markdown → HTML for plugin descriptions (bold, code, links, newlines). */
export function mdToHtml(src) {
  let s = esc(src);
  // links [text](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" rel="noopener" target="_blank">$1</a>');
  // bold **text** or __text__
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/__([^_]+)__/g, '<strong>$1</strong>');
  // inline code `code`
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // italics *text* (after bold)
  s = s.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,]|$)/g, '$1<em>$2</em>');
  // paragraphs on blank lines
  const parts = s.split(/\n{2,}/).map((p) => p.replace(/\n/g, '<br>'));
  return parts.map((p) => `<p>${p}</p>`).join('');
}

const SLOT = {
  Developer: 'Tools', 'AI Models': 'Model', 'UI & Skins': 'UI', Knowledge: 'Skills',
  Desktop: 'Desktop', Automation: 'Workflow', Network: 'Integrations', Browser: 'Browser',
  Terminal: 'Terminal', Storage: 'Storage', Vision: 'Vision', Data: 'Data',
  Security: 'Security', Productivity: 'Productivity', Content: 'Content',
};

function navHtml(zh, langSwitchHref) {
  if (zh) {
    return `<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="/zh/"><img class="brand-logo" src="/logo.svg" alt="dshbase logo" width="30" height="30"><span>dsh</span><strong>base</strong></a>
    <nav class="nav" aria-label="主导航">
      <a class="nav-link" href="/zh/tutorial/">教程</a>
      <a class="nav-link" href="/zh/plugins/">插件</a>
      <a class="nav-link" href="/zh/plugins/directory/">目录</a>
      <a class="nav-link" href="/zh/blog/">博客</a>
      <a class="nav-link" href="/zh/install/">安装</a>
      <details class="nav-dd"><summary class="nav-link nav-dd-sum">生态</summary>
        <div class="nav-dd-menu" role="group"><a href="/zh/packs/">合集</a><a href="/zh/themes/">主题</a><a href="/zh/contributors/">贡献者</a></div>
      </details>
      <details class="nav-dd"><summary class="nav-link nav-dd-sum">更多</summary>
        <div class="nav-dd-menu" role="group"><a href="/zh/audit/">审计</a><a href="/zh/troubleshooting/">排错</a></div>
      </details>
    </nav>
    <div class="nav-tools">
      <a href="${esc(langSwitchHref)}" class="lang-switch" hreflang="en" lang="en" aria-label="Switch to English" title="Switch to English">EN</a>
    </div>
  </div>
</header>`;
  }
  return `<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="/"><img class="brand-logo" src="/logo.svg" alt="dshbase logo" width="30" height="30"><span>dsh</span><strong>base</strong></a>
    <nav class="nav" aria-label="Main">
      <a class="nav-link" href="/tutorial/">Tutorial</a>
      <a class="nav-link" href="/plugins/">Plugins</a>
      <a class="nav-link" href="/plugins/directory/">Directory</a>
      <a class="nav-link" href="/blog/">Blog</a>
      <a class="nav-link" href="/install/">Install</a>
      <details class="nav-dd"><summary class="nav-link nav-dd-sum">Ecosystem</summary>
        <div class="nav-dd-menu" role="group"><a href="/packs/">Packs</a><a href="/themes/">Themes</a><a href="/contributors/">Contributors</a></div>
      </details>
      <details class="nav-dd"><summary class="nav-link nav-dd-sum">More</summary>
        <div class="nav-dd-menu" role="group"><a href="/audit/">Audit</a><a href="/troubleshooting/">Troubleshooting</a></div>
      </details>
    </nav>
    <div class="nav-tools">
      <a href="${esc(langSwitchHref)}" class="lang-switch" hreflang="zh-CN" lang="zh-CN" aria-label="Switch to Chinese" title="Switch to Chinese">中文</a>
    </div>
  </div>
</header>`;
}

function footerHtml(zh) {
  if (zh) {
    return `<footer class="foot">
  <div class="wrap foot-grid">
    <div class="foot-col">
      <p class="foot-brand"><img class="foot-logo" src="/logo.svg" alt="dshbase logo" width="24" height="24"><span>dsh</span><strong>base</strong></p>
      <p class="muted small">DeepSeek Harness 中文指南、教程与插件生态。</p>
    </div>
    <div class="foot-col"><b>指南</b><a href="/zh/tutorial/">教程</a><a href="/zh/install/">安装</a><a href="/zh/plugins/">插件</a><a href="/zh/troubleshooting/">排错</a></div>
    <div class="foot-col"><b>资源</b><a href="/zh/plugins/directory/">插件目录</a><a href="/zh/packs/">合集</a><a href="/zh/themes/">主题</a><a href="/zh/blog/">博客</a></div>
    <div class="foot-col"><b>关于</b><a href="/zh/about/">关于</a><a href="/zh/contact/">联系</a><a href="/zh/privacy/">隐私</a></div>
  </div>
  <div class="wrap foot-in"><p class="muted small">非官方社区资源。与 DeepSeek 无关。</p></div>
</footer>`;
  }
  return `<footer class="foot">
  <div class="wrap foot-grid">
    <div class="foot-col">
      <p class="foot-brand"><img class="foot-logo" src="/logo.svg" alt="dshbase logo" width="24" height="24"><span>dsh</span><strong>base</strong></p>
      <p class="muted small">DeepSeek Harness guides, tutorials &amp; plugin ecosystem.</p>
    </div>
    <div class="foot-col"><b>Guides</b><a href="/tutorial/">Tutorial</a><a href="/install/">Install</a><a href="/plugins/">Plugins</a><a href="/troubleshooting/">Troubleshooting</a></div>
    <div class="foot-col"><b>Resources</b><a href="/plugins/directory/">Plugin directory</a><a href="/packs/">Packs</a><a href="/themes/">Themes</a><a href="/blog/">Blog</a></div>
    <div class="foot-col"><b>About</b><a href="/about/">About</a><a href="/contact/">Contact</a><a href="/privacy/">Privacy</a></div>
  </div>
  <div class="wrap foot-in"><p class="muted small">Unofficial community resource. Not affiliated with DeepSeek.</p></div>
</footer>`;
}

export function renderPluginPage(p, lang) {
  const zh = lang === 'zh';
  const cat = p.cat || 'Plugin';
  const slot = SLOT[cat] || 'Plugin';
  const name = p.name || p.slug;
  const descRaw = zh ? (p.desc_zh || p.desc || name) : (p.desc || p.desc_zh || name);
  const descHtml = mdToHtml(descRaw);
  const descMeta = esc(String(descRaw).replace(/\s+/g, ' ').replace(/\*+/g, '').slice(0, 160));
  const title = zh
    ? `${esc(name)} — ${esc(slot)} 插件 · DeepSeek Harness | dshbase`
    : `${esc(name)} — ${esc(slot)} plugin for DeepSeek Harness | dshbase`;
  const path = zh ? `/zh/plugins/${p.slug}/` : `/plugins/${p.slug}/`;
  const twin = zh ? `/plugins/${p.slug}/` : `/zh/plugins/${p.slug}/`;
  const dir = zh ? '/zh/plugins/directory/' : '/plugins/directory/';
  const catId = String(cat).toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const catUrl = `${dir}page/1/#${catId}`;
  const repo = (p.url || '').replace(/^https?:\/\/github\.com\//, '');
  const install = p.npm && p.pkg
    ? `dsh plugin --profile web add ${p.pkg}`
    : `dsh plugin --profile web add github:${repo}`;
  const verified = p.test === 'verified';
  const statusLabel = zh
    ? (verified ? '已验证 · 已在 dsh 上安装测试' : '未验证')
    : (verified ? 'Verified · install-tested on dsh' : 'Unverified');
  const statusClass = verified ? 'st-ok' : 'st-warn';
  const stars = p.stars ?? 0;
  const enCanon = `https://dshbase.com/plugins/${esc(p.slug)}/`;
  const zhCanon = `https://dshbase.com/zh/plugins/${esc(p.slug)}/`;
  const canonical = zh ? zhCanon : enCanon;
  const jsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name,
    description: String(descRaw).replace(/\*+/g, '').slice(0, 300),
    url: canonical,
    applicationCategory: 'DeveloperApplication',
    operatingSystem: 'Web',
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  });

  const t = zh
    ? {
        dir: '插件目录',
        what: '它做什么',
        install: '安装',
        github: '在 GitHub 查看',
        back: '← 返回插件目录',
        catalog: '让 Agent 自动安装（推荐）',
        catalogHint: '先安装目录插件，然后对 DeepSeek Harness 说「帮我安装这个插件」即可。',
        take: '我们的判断',
        takeBody: verified
          ? '已验证 — CI 在干净环境中成功执行了 dsh plugin add。'
          : '未验证 — 尚未完成安装测试，请自行评估。',
        honest: '「已验证」仅表示我们的自动化流水线跑通了安装与启动，不是安全审计，也不是对第三方代码的背书。',
      }
    : {
        dir: 'Plugin directory',
        what: 'What it does',
        install: 'Install',
        github: 'View on GitHub',
        back: '← Back to plugin directory',
        catalog: 'Let your agent install it (recommended)',
        catalogHint: 'Install the catalog once, then ask DeepSeek Harness to find and install this plugin.',
        take: 'Our take',
        takeBody: verified
          ? 'Works — verified: CI ran dsh plugin add in a clean profile and it booted.'
          : 'Unverified — not yet install-tested; try it in your own environment.',
        honest: '“Verified” means our CI ran dsh plugin add in a clean profile and it booted — not a security audit and not an endorsement of third-party code.',
      };

  const html = `<!doctype html>
<html lang="${zh ? 'zh-CN' : 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<meta name="description" content="${descMeta}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="googlebot" content="noindex, follow">
<link rel="canonical" href="${canonical}">
<link rel="alternate" hreflang="en" href="${enCanon}">
<link rel="alternate" hreflang="zh-CN" href="${zhCanon}">
<link rel="alternate" hreflang="x-default" href="${enCanon}">
<link rel="icon" href="/logo.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="dshbase">
<meta property="og:title" content="${title}">
<meta property="og:description" content="${descMeta}">
<meta property="og:url" content="${canonical}">
<meta property="og:image" content="https://dshbase.com/og.png">
<meta property="og:locale" content="${zh ? 'zh_CN' : 'en_US'}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${title}">
<meta name="twitter:description" content="${descMeta}">
<meta name="twitter:image" content="https://dshbase.com/og.png">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/styles/global.css">
<script type="application/ld+json">${jsonLd}</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-YVWXYEDWK5"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-YVWXYEDWK5');</script>
</head>
<body>
<div class="app">
${navHtml(zh, twin)}
<script type="module">
const t=Array.from(document.querySelectorAll("details.nav-dd"));
t.forEach(e=>{e.addEventListener("toggle",()=>{e.open&&t.forEach(n=>{n!==e&&(n.open=!1)})})});
document.addEventListener("click",e=>{const n=e.target;(!(n instanceof Element)||!n.closest("details.nav-dd"))&&t.forEach(a=>{a.open=!1})});
document.addEventListener("keydown",e=>{e.key==="Escape"&&t.forEach(n=>{n.open=!1})});
</script>
<main>
  <section class="hero wrap">
    <p class="eyebrow"><a href="${dir}">${t.dir}</a> / <a href="${catUrl}">${esc(cat)}</a> / ${esc(name)}</p>
    <h1>${esc(name)}</h1>
    <p class="lede"><span class="badge ${statusClass}">${statusLabel}</span></p>
    <p style="margin-top:14px" class="btn-row">
      ${p.url ? `<a class="btn btn-ghost btn-sm" href="${esc(p.url)}" target="_blank" rel="noopener">${t.github} ↗</a> ` : ''}
      <a class="btn btn-ghost btn-sm" href="${dir}">${t.back}</a>
    </p>
  </section>

  <section class="wrap">
    <div class="metrics">
      <div class="metric"><span class="m-val">${stars}</span><span class="m-lab">${zh ? '星标' : 'Stars'}</span></div>
      <div class="metric"><span class="m-val">${esc(cat)}</span><span class="m-lab">${zh ? '分类' : 'Category'}</span></div>
      <div class="metric"><span class="m-val">${p.npm ? 'npm' : 'GitHub'}</span><span class="m-lab">${zh ? '来源' : 'Source'}</span></div>
    </div>
  </section>

  <section class="detail-grid wrap">
    <div class="dg-main">
      <h2>${t.what}</h2>
      <div class="what-it-does">${descHtml}</div>
      <div class="verdict ${verified ? 'v-ok' : 'v-warn'}">
        <span class="v-icon">${verified ? '✅' : '⏳'}</span>
        <div><strong>${t.take}</strong><br/>${t.takeBody}</div>
      </div>
      <p class="honest-note">${t.honest}</p>
    </div>
    <div class="dg-side">
      <div class="side-card">
        <h2>${t.install}</h2>
        <div class="catalog-box">
          <strong>🧩 ${t.catalog}</strong>
          <p>${t.catalogHint}</p>
          <pre class="code-block"><code>dsh plugin add dshbase-catalog</code></pre>
        </div>
        <p class="muted small">${zh ? 'Web 配置：' : 'Web profile:'}</p>
        <pre class="code-block"><code>${esc(install)}</code></pre>
        ${p.url ? `<p style="margin-top:14px"><a href="${esc(p.url)}" rel="noopener" target="_blank">${t.github} ↗</a></p>` : ''}
      </div>
    </div>
  </section>
</main>
${footerHtml(zh)}
</div>
<script type="module">
document.querySelectorAll("pre.code-block").forEach(t=>{
  if(t.querySelector(".copy-btn"))return;
  const e=document.createElement("button");
  e.className="copy-btn";e.textContent="Copy";e.type="button";
  e.addEventListener("click",async()=>{
    const d=t.querySelector("code")?.textContent||"";
    try{await navigator.clipboard.writeText(d);e.textContent="Copied!"}catch{e.textContent="Failed"}
    setTimeout(()=>{e.textContent="Copy"},1500);
  });
  t.style.position="relative";t.appendChild(e);
});
</script>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=300',
    },
  });
}
