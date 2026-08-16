// Full-site search index (prerendered to /search-index.json).
// Consumed by src/components/Search.astro for the ⌘K command palette.
import type { APIRoute } from 'astro';
import plugins from '../data/plugins.json';
import blogPosts from '../data/blog-posts.json';

const repo = (u: string) => (u || '').replace('https://github.com/', '');
const owner = (u: string) => (u || '').replace('https://github.com/', '').split('/')[0] || '';

// Static pages (path is the canonical en route; zh is derived client-side via `/zh` prefix).
const PAGES: Array<{ path: string; title: string; title_zh: string; desc: string; desc_zh: string }> = [
  { path: '/', title: 'Home', title_zh: '首页', desc: 'DeepSeek Harness guides, tutorials & plugin ecosystem.', desc_zh: 'DeepSeek Harness 指南、教程与插件生态。' },
  { path: '/tutorial/', title: 'Tutorial', title_zh: '教程', desc: 'Getting started with DeepSeek Harness.', desc_zh: 'DeepSeek Harness 快速上手。' },
  { path: '/plugins/', title: 'Plugins', title_zh: '插件', desc: 'How the DeepSeek Harness plugin system works.', desc_zh: 'DeepSeek Harness 插件系统工作原理。' },
  { path: '/plugins/directory/', title: 'Plugin directory', title_zh: '插件目录', desc: 'Browse the plugin ecosystem: categories, use cases, install commands.', desc_zh: '浏览插件生态：分类、使用场景、安装命令。' },
  { path: '/plugins/compare/', title: 'Compare plugins', title_zh: '插件对比', desc: 'Compare DeepSeek Harness plugins side by side.', desc_zh: '并排对比 DeepSeek Harness 插件。' },
  { path: '/themes/', title: 'Themes & skins', title_zh: '皮肤主题', desc: 'Community themes and skins.', desc_zh: '社区皮肤与主题。' },
  { path: '/advanced-skins/', title: 'Advanced skins', title_zh: '高级皮肤', desc: 'Advanced skin customization.', desc_zh: '高级皮肤定制。' },
  { path: '/install/', title: 'Install', title_zh: '安装', desc: 'Install DeepSeek Harness and plugins.', desc_zh: '安装 DeepSeek Harness 与插件。' },
  { path: '/troubleshooting/', title: 'Troubleshooting', title_zh: '排错', desc: 'Fix common DeepSeek Harness problems.', desc_zh: '解决 DeepSeek Harness 常见问题。' },
  { path: '/blog/', title: 'Blog', title_zh: '博客', desc: 'Guides, comparisons, and analysis.', desc_zh: '指南、对比与分析。' },
  { path: '/about/', title: 'About', title_zh: '关于', desc: 'About dshbase.', desc_zh: '关于 dshbase。' },
  { path: '/contact/', title: 'Contact', title_zh: '联系', desc: 'Contact dshbase.', desc_zh: '联系 dshbase。' },
  { path: '/privacy/', title: 'Privacy', title_zh: '隐私', desc: 'Privacy policy.', desc_zh: '隐私政策。' },
];

export const GET: APIRoute = () => {
  const pluginList: Array<Record<string, unknown>> = [];
  for (const [cat, items] of Object.entries(plugins as Record<string, Array<Record<string, unknown>>>)) {
    for (const p of items) {
      const name = (p.name as string) || '';
      const slug = (p.slug as string) || name;
      const descEn = (p.desc_en as string) || (p.desc as string) || '';
      const descZh = (p.desc_zh as string) || '';
      const ucs = (p.ucs as string[]) || [];
      const license = (p.license as string) || '';
      const cmd = (p.npm && p.pkg)
        ? `dsh plugin add ${p.pkg}`
        : `dsh plugin add github:${repo(p.url as string)}`;
      const q = `${name} ${owner(p.url as string)} ${p.pkg || ''} ${descEn} ${descZh} ${cat} ${ucs.join(' ')} ${license}`.toLowerCase();
      pluginList.push({
        name,
        slug,
        owner: owner(p.url as string),
        desc: descEn,
        desc_zh: descZh,
        cat,
        ucs,
        stars: p.stars ?? 0,
        test: p.test || 'pending',
        cmd,
        q,
      });
    }
  }

  const posts = blogPosts.map((b) => ({
    path: b.path,
    title: b.en,
    title_zh: b.zh || '',
    desc: b.desc_en,
    desc_zh: b.desc_zh || '',
    q: `${b.en} ${b.zh} ${b.desc_en} ${b.desc_zh} ${b.cat}`.toLowerCase(),
  }));

  const pages = PAGES.map((p) => ({
    ...p,
    q: `${p.title} ${p.title_zh} ${p.desc} ${p.desc_zh}`.toLowerCase(),
  }));

  return new Response(JSON.stringify({ plugins: pluginList, posts, pages }), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
};
