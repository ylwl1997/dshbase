#!/usr/bin/env python3
"""回补 4 个恢复插件在博客里的链接（上轮误删时被 de-link）。
对每个 en/zh 博客文件：补回 const XUrl 行 + 把 <strong>NAME</strong> 还原成 <a href={XUrl}>NAME</a>。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_DIRS = [
    (os.path.join(ROOT, 'src', 'pages', 'blog'), 'en'),
    (os.path.join(ROOT, 'src', 'pages', 'zh', 'blog'), 'zh'),
]
# name -> (varName, slug)
PLUGINS = {
    'dsh-data-agent': ('dataAgent', 'dsh-data-agent'),
    'dsh-interconnect': ('interconnect', 'dsh-interconnect'),
    'dsh-security-audit': ('audit', 'dsh-security-audit'),
    'dsh-vision-toolkit': ('visionToolkit', 'dsh-vision-toolkit'),
}

changed = []
for d, locale in BLOG_DIRS:
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.astro'):
            continue
        fp = os.path.join(d, fn)
        txt = open(fp, encoding='utf-8').read()
        orig = txt
        for name, (var, slug) in PLUGINS.items():
            urlvar = f'{var}Url'
            # 只在有 de-link 痕迹（<strong>NAME</strong> 且无 const 行）时回补
            if f'<strong>{name}</strong>' in txt and f'{urlvar} =' not in txt:
                # 1) 补 const 行（插到最后一个 getRelativeLocaleUrl const 之后，或 import 之后）
                const_line = f"const {urlvar} = getRelativeLocaleUrl('{locale}', '/plugins/{slug}/');"
                m = list(re.finditer(r"^const \w+ = getRelativeLocaleUrl\([^\n]+$", txt, re.M))
                if m:
                    ins = m[-1].end()
                    txt = txt[:ins] + '\n' + const_line + txt[ins:]
                else:
                    imp = txt.find('\n', txt.find('import'))
                    txt = txt[:imp] + '\n' + const_line + txt[imp:]
                # 2) 回补 <a> 包裹
                txt = txt.replace(
                    f'<strong>{name}</strong>',
                    f'<strong><a href={{{urlvar}}}>{name}</a></strong>'
                )
        if txt != orig:
            open(fp, 'w', encoding='utf-8').write(txt)
            changed.append(fp)

print(f'修改 {len(changed)} 个文件:')
for c in changed:
    print('  ', os.path.relpath(c, ROOT))
