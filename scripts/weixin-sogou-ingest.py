#!/usr/bin/env python3
"""搜狗微信搜索 → 改写（非原文搬运）→ 发布 dshbase 双语博客。

用法（推荐在已登录浏览器的 VPS / 本机跑，需 bsk）:
  python scripts/weixin-sogou-ingest.py --search-only
  python scripts/weixin-sogou-ingest.py --dry-run --limit 5
  python scripts/weixin-sogou-ingest.py --publish --limit 3

环境:
  DEEPSEEK_API_KEY  或 ~/.dsh/.credentials.yaml 中的 DEEPSEEK_API_KEY
  WEIXIN_INGEST_BSK=0  强制跳过 bsk（仅 HTTP，搜狗常失败）

版权约束:
  - 只产出改写/分析稿，禁止把微信正文大段 verbatim 写入 Astro
  - 原文链接仅作「参考/线索」
  - 低相关 / 软广 / 重复主题自动跳过

状态文件: src/data/weixin-ingest-state.json
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_PATH = os.path.join(ROOT, "src", "data", "weixin-ingest-state.json")
BLOG_POSTS = os.path.join(ROOT, "src", "data", "blog-posts.json")
EN_INDEX = os.path.join(ROOT, "src", "pages", "blog", "index.astro")
ZH_INDEX = os.path.join(ROOT, "src", "pages", "zh", "blog", "index.astro")
EN_BLOG = os.path.join(ROOT, "src", "pages", "blog")
ZH_BLOG = os.path.join(ROOT, "src", "pages", "zh", "blog")

DEFAULT_QUERIES = [
    "DeepSeek Harness",
    "DeepSeek Harness rc.8",
    "DSH 插件",
    "dsh插件",
    "DeepSeek Harness 多模态",
    "DeepSeek Harness 命令",
]

# 标题/摘要命中任一项才算相关；命中广告词降分
RELEVANT_RE = re.compile(
    r"deepseek\s*harness|deepseek-harness|\bdsh\b|dsh插件|dsh\s*plugin|"
    r"cordis|rc\.?8|多模态|harness",
    re.I,
)
AD_RE = re.compile(
    r"招聘|求职|内推|课程报名|扫码进群|优惠券|限时免费|加微信领|"
    r"代写|刷单|兼职日结|引流",
    re.I,
)
# 已有站内改写主题，避免再发近似文
COVERED_TITLE_HINTS = [
    "一切皆插件",
    "大起底",
    "重新定义「插件」",
    "重新定义插件",
    "30.2",
    "96.2",
    "爆肝实测",
    "第一天",
    "真实的第一天",
]

CAT_MAP = {
    "Guide": ("Guide", "指南"),
    "Analysis": ("Analysis", "分析"),
    "Concept": ("Concept", "概念"),
    "Review": ("Review", "评测"),
    "Tutorial": ("Tutorial", "教程"),
    "Pulse": ("Pulse", "脉搏"),
}


def log(msg: str) -> None:
    print(msg, flush=True)


def read_dsk() -> str:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"].strip()
    cred = os.path.expanduser("~/.dsh/.credentials.yaml")
    if os.path.isfile(cred):
        txt = open(cred, encoding="utf-8").read()
        m = re.search(r"DEEPSEEK_API_KEY:\s*(\S+)", txt)
        if m:
            return m.group(1).strip()
    raise SystemExit("缺少 DEEPSEEK_API_KEY（环境变量或 ~/.dsh/.credentials.yaml）")


def load_json(path: str, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # Match repo style for blog-posts.json (indent=1) vs state (indent=2)
        indent = 1 if path.endswith("blog-posts.json") else 2
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def slugify(text: str, prefix: str = "wx-") -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9一-龥]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    # ASCII-only slug for URLs
    ascii_parts = re.findall(r"[a-z0-9]+", s)
    base = "-".join(ascii_parts)[:48] or "dsh-note"
    slug = f"{prefix}{base}"
    # uniqueness
    n = 1
    candidate = slug
    while os.path.isfile(os.path.join(EN_BLOG, f"{candidate}.astro")):
        n += 1
        candidate = f"{slug}-{n}"
    return candidate


def existing_blog_titles() -> set[str]:
    titles: set[str] = set()
    posts = load_json(BLOG_POSTS, [])
    for p in posts:
        for k in ("en", "zh"):
            if p.get(k):
                titles.add(p[k].strip().lower())
    for d in (EN_BLOG, ZH_BLOG):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.endswith(".astro") and fn != "index.astro":
                titles.add(fn[:-6].replace("-", " ").lower())
    return titles


def load_state() -> dict:
    st = load_json(STATE_PATH, {"seen": [], "published": []})
    st.setdefault("seen", [])
    st.setdefault("published", [])
    return st


def norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def is_duplicate(item: dict, state: dict, titles: set[str]) -> str | None:
    title = norm_title(item.get("title", ""))
    href = (item.get("href") or "").strip()
    for s in state["seen"] + state["published"]:
        if href and s.get("href") == href:
            return "seen-url"
        if title and norm_title(s.get("title", "")) == title:
            return "seen-title"
    for hint in COVERED_TITLE_HINTS:
        if hint.lower() in title:
            return f"covered-theme:{hint}"
    for t in titles:
        if title and (title in t or t in title) and len(title) > 8:
            return "blog-title-overlap"
    return None


def score_item(item: dict) -> float:
    blob = f"{item.get('title','')} {item.get('snippet','')} {item.get('account','')}"
    if not RELEVANT_RE.search(blob):
        return 0.0
    score = 1.0
    if re.search(r"deepseek\s*harness|deepseek-harness", blob, re.I):
        score += 2.0
    if re.search(r"\bdsh\b|插件|plugin|rc\.?8|命令|多模态|实测|拆解", blob, re.I):
        score += 1.0
    if AD_RE.search(blob):
        score -= 3.0
    # soft ads in account names
    if AD_RE.search(item.get("account") or ""):
        score -= 1.5
    return score


# ---------- bsk helpers ----------

def bsk_available() -> bool:
    if os.environ.get("WEIXIN_INGEST_BSK", "1") == "0":
        return False
    try:
        r = subprocess.run(
            ["bsk", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False


def bsk_run(args: list[str], timeout: int = 90) -> str:
    r = subprocess.run(
        ["bsk", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
    if r.returncode != 0:
        raise RuntimeError(f"bsk {' '.join(args[:3])} failed ({r.returncode}): {out[-800:]}")
    return r.stdout or ""


def bsk_json(args: list[str], timeout: int = 90):
    raw = bsk_run([*args, "--json"], timeout=timeout)
    raw = raw.strip()
    # bsk may print non-json warnings; find last JSON object/array
    for opener, closer in (("{", "}"), ("[", "]")):
        i = raw.rfind(opener)
        if i >= 0:
            try:
                return json.loads(raw[i:])
            except json.JSONDecodeError:
                pass
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"bsk JSON parse failed: {e}; tail={raw[-400:]}") from e


def with_bsk_session(fn):
    """Start session, run fn(session_id), always stop."""
    data = bsk_json(["session", "start"])
    sid = data.get("session_id") or data.get("id")
    if not sid:
        raise RuntimeError(f"no session_id from bsk: {data}")
    try:
        return fn(sid)
    finally:
        try:
            subprocess.run(
                ["bsk", "session", "stop", sid],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            pass


EXTRACT_LIST_JS = r"""(() => {
  const nodes = [...document.querySelectorAll('ul.news-list > li')];
  const boxes = nodes.length ? nodes : [...document.querySelectorAll('.news-box .txt-box')];
  return boxes.slice(0, 25).map((el, i) => {
    const box = el.querySelector ? (el.querySelector('.txt-box') || el) : el;
    const a = box.querySelector('h3 a') || box.querySelector('a');
    const acctEl = box.querySelector('.account') || box.querySelector('a[uigs]');
    const snEl = box.querySelector('p.txt-info') || box.querySelector('p');
    const timeEl = box.querySelector('.s2') || box.querySelector('span.s2');
    return {
      i,
      title: ((a && a.textContent) || '').trim(),
      href: (a && a.href) || '',
      account: ((acctEl && acctEl.textContent) || '').trim(),
      snippet: ((snEl && snEl.textContent) || '').trim().slice(0, 220),
      time: ((timeEl && timeEl.textContent) || '').trim(),
    };
  });
})()"""


EXTRACT_ARTICLE_JS = r"""(() => {
  const url = location.href;
  const title = (document.querySelector('#activity-name')
    || document.querySelector('.rich_media_title')
    || document.querySelector('h1')
    || document.querySelector('title')
    || {textContent: document.title}).textContent.trim();
  const account = (document.querySelector('#js_name')
    || document.querySelector('.profile_nickname')
    || {textContent: ''}).textContent.trim();
  const body = document.querySelector('#js_content')
    || document.querySelector('.rich_media_content')
    || document.querySelector('article')
    || document.body;
  let text = (body && body.innerText) || '';
  text = text.replace(/\n{3,}/g, '\n\n').trim();
  const captcha = !!(document.querySelector('#seccodeImage')
    || /验证码|请输入验证|security verification/i.test(document.body.innerText || ''));
  const blocked = captcha || text.length < 80;
  return {
    url, title, account,
    textLen: text.length,
    text: text.slice(0, 12000),
    captcha, blocked,
  };
})()"""


def search_sogou_bsk(queries: list[str]) -> list[dict]:
    def work(sid: str) -> list[dict]:
        seen_href = set()
        out: list[dict] = []
        for q in queries:
            url = "https://weixin.sogou.com/weixin?type=2&query=" + urllib.parse.quote(q)
            log(f"  search: {q}")
            # sogou pages often hang on networkidle; prefer commit/domcontentloaded
            try:
                bsk_run(
                    [
                        "navigate",
                        url,
                        "--session",
                        sid,
                        "--timeout",
                        "90s",
                        "--wait-until",
                        "domcontentloaded",
                    ],
                    timeout=100,
                )
            except RuntimeError:
                bsk_run(
                    [
                        "navigate",
                        url,
                        "--session",
                        sid,
                        "--timeout",
                        "90s",
                        "--wait-until",
                        "commit",
                    ],
                    timeout=100,
                )
            time.sleep(2.5)
            ev = bsk_json(
                ["evaluate", "--session", sid, EXTRACT_LIST_JS],
                timeout=60,
            )
            items = ev.get("value") if isinstance(ev, dict) else ev
            if isinstance(items, str):
                items = json.loads(items)
            if not isinstance(items, list):
                log(f"    warn: unexpected evaluate result for {q}")
                continue
            for it in items:
                href = (it.get("href") or "").strip()
                if not href or href in seen_href:
                    continue
                seen_href.add(href)
                it["query"] = q
                it["score"] = score_item(it)
                out.append(it)
            time.sleep(1.2)
        return out

    return with_bsk_session(work)


def search_sogou_http(queries: list[str]) -> list[dict]:
    """Fragile fallback — Sogou often returns captcha / empty HTML."""
    out: list[dict] = []
    seen = set()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    for q in queries:
        url = "https://weixin.sogou.com/weixin?type=2&query=" + urllib.parse.quote(q)
        log(f"  http search: {q}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=25) as r:
                html_txt = r.read().decode("utf-8", "replace")
        except Exception as e:
            log(f"    fail: {e}")
            continue
        # very light parse
        for m in re.finditer(
            r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html_txt,
            re.I | re.S,
        ):
            href = html.unescape(m.group(1))
            title = re.sub(r"<[^>]+>", "", m.group(2))
            title = html.unescape(re.sub(r"\s+", " ", title)).strip()
            if not href.startswith("http"):
                href = urllib.parse.urljoin("https://weixin.sogou.com", href)
            if href in seen:
                continue
            seen.add(href)
            it = {"title": title, "href": href, "account": "", "snippet": "", "query": q}
            it["score"] = score_item(it)
            out.append(it)
        time.sleep(1.5)
    return out


def fetch_article_bsk(href: str) -> dict:
    def work(sid: str) -> dict:
        try:
            bsk_run(
                [
                    "navigate",
                    href,
                    "--session",
                    sid,
                    "--timeout",
                    "90s",
                    "--wait-until",
                    "domcontentloaded",
                ],
                timeout=100,
            )
        except RuntimeError:
            bsk_run(
                [
                    "navigate",
                    href,
                    "--session",
                    sid,
                    "--timeout",
                    "90s",
                    "--wait-until",
                    "commit",
                ],
                timeout=100,
            )
        time.sleep(3.5)
        # follow sogou intermediate pages once
        for _ in range(2):
            ev = bsk_json(
                ["evaluate", "--session", sid, EXTRACT_ARTICLE_JS],
                timeout=60,
            )
            art = ev.get("value") if isinstance(ev, dict) else ev
            if isinstance(art, str):
                art = json.loads(art)
            if not art.get("blocked") and art.get("textLen", 0) > 200:
                return art
            # try click continue / link to weixin
            click_js = r"""(() => {
              const a = document.querySelector('a#js_link')
                || document.querySelector('a[href*="mp.weixin.qq.com"]')
                || [...document.querySelectorAll('a')].find(x => /阅读全文|继续|查看原文/.test(x.textContent||''));
              if (a) { a.click(); return true; }
              return false;
            })()"""
            clicked = bsk_json(["evaluate", "--session", sid, click_js], timeout=30)
            val = clicked.get("value") if isinstance(clicked, dict) else clicked
            if not val:
                break
            time.sleep(3)
        return art if isinstance(art, dict) else {"blocked": True, "text": "", "title": "", "url": href}

    return with_bsk_session(work)


def llm_json(prompt: str, temperature: float = 0.45) -> dict:
    data = json.dumps(
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=data,
        headers={
            "Authorization": "Bearer " + read_dsk(),
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        content = json.loads(r.read())["choices"][0]["message"]["content"]
    return json.loads(content)


def rewrite_article(meta: dict, source_text: str) -> dict | None:
    """Transformative rewrite for dshbase audience. Never ask for verbatim copy."""
    # Cap source for model; still instruct no long quotes
    src = source_text[:9000]
    prompt = f"""你是 dshbase（DeepSeek Harness 插件目录站）的编辑。根据下面「线索摘要」（来自微信公众号文章的要点摘录，可能不完整），写一篇**完全改写**的双语博客。

硬性规则:
1. 禁止大段照抄原文；禁止连续引用超过 25 个汉字/词的原文句子。
2. 面向安装者：可操作、诚实、少营销腔；可链接 dshbase 目录/审计理念。
3. 若线索像招聘/卖课/无关软广，返回 {{"skip": true, "reason": "..."}}。
4. 若与「一切皆插件大起底 / 30.2→96.2 harness / 第一天上手」高度重复，返回 skip。
5. HTML 正文只用 <p><h2><ul><li><strong><code><a>；不要 <script>/<style>/<img>。
6. slug 必须是英文 kebab-case，以 wx- 开头，简短独特。

线索元数据:
- 标题: {meta.get('title')}
- 公众号: {meta.get('account')}
- 搜索词: {meta.get('query')}
- 源链: {meta.get('final_url') or meta.get('href')}

线索正文摘录（仅供理解主题，勿照抄）:
\"\"\"
{src}
\"\"\"

返回 JSON:
{{
  "skip": false,
  "slug": "wx-...",
  "category": "Guide|Analysis|Concept|Review|Tutorial|Pulse",
  "title_en": "...",
  "title_zh": "...",
  "desc_en": "≤160 chars",
  "desc_zh": "≤80 字",
  "body_en_html": "若干 <h2>/<p>/<ul>...",
  "body_zh_html": "若干 <h2>/<p>/<ul>...",
  "source_note_en": "one short sentence crediting the WeChat clue without copying",
  "source_note_zh": "一句中文说明：改写自微信线索，非原文搬运"
}}
"""
    for attempt in range(3):
        try:
            obj = llm_json(prompt)
            if obj.get("skip"):
                return obj
            need = [
                "slug", "category", "title_en", "title_zh",
                "desc_en", "desc_zh", "body_en_html", "body_zh_html",
            ]
            if all(obj.get(k) for k in need):
                if not str(obj["slug"]).startswith("wx-"):
                    obj["slug"] = "wx-" + re.sub(r"[^a-z0-9-]", "", obj["slug"].lower())
                return obj
        except Exception as e:
            log(f"  rewrite retry: {e}")
        time.sleep(2)
    return None


def escape_attr(s: str) -> str:
    return html.escape(s or "", quote=True)


def render_astro(
    locale: str,
    slug: str,
    category_label: str,
    title: str,
    description: str,
    h1_html: str,
    date_label: str,
    source_note: str,
    source_url: str,
    body_html: str,
) -> str:
    if locale == "en":
        layout = "../../layouts/BlogPost.astro"
        dir_url = "en"
        credit = "rewritten field note"
        ref_label = "Source clue (WeChat via Sogou; not a verbatim reprint)"
    else:
        layout = "../../../layouts/BlogPost.astro"
        dir_url = "zh"
        credit = "改写解读"
        ref_label = "参考/线索（微信；非原文搬运）"

    # Light internal links
    imports = (
        f"---\nimport BlogPost from '{layout}';\n"
        f"import {{ getRelativeLocaleUrl }} from 'astro:i18n';\n"
        f"const directoryUrl = getRelativeLocaleUrl('{dir_url}', '/plugins/directory/');\n"
        f"const auditUrl = getRelativeLocaleUrl('{dir_url}', '/audit/');\n"
        f"---\n"
    )
    # Inject directory mention if missing
    if "directoryUrl" not in body_html and "plugins/directory" not in body_html:
        if locale == "en":
            extra = (
                '<h2>On dshbase</h2>\n'
                '<p>Before installing random GitHub plugins, check the '
                '<a href={directoryUrl}>verified directory</a> and '
                '<a href={auditUrl}>audit notes</a>.</p>\n'
            )
        else:
            extra = (
                '<h2>在 dshbase 上</h2>\n'
                '<p>装随机 GitHub 插件前，先看'
                '<a href={directoryUrl}>已验证目录</a>与'
                '<a href={auditUrl}>审计说明</a>。</p>\n'
            )
        body_html = body_html.rstrip() + "\n" + extra

    src_block = ""
    if source_url:
        src_block = (
            f'  <p class="muted small"><a href="{escape_attr(source_url)}" '
            f'rel="noopener noreferrer nofollow" target="_blank">{ref_label}</a>'
            f" — {html.escape(source_note or '')}</p>\n"
        )

    return (
        f"{imports}"
        f"<BlogPost title=\"{escape_attr(title)} | dshbase{' 中文' if locale=='zh' else ''}\" "
        f"description=\"{escape_attr(description)}\" "
        f"currentPath=\"/blog/{slug}/\" category=\"{escape_attr(category_label)}\">\n"
        f"  {h1_html}\n"
        f"  <p class=\"muted small\" style=\"margin-bottom:20px\">{date_label} · dshbase · {credit}</p>\n"
        f"  <p class=\"muted small\">{html.escape(source_note or '')}</p>\n"
        f"{src_block}"
        f"{body_html}\n"
        f"</BlogPost>\n"
    )


def accent_h1(title: str, locale: str) -> str:
    # Wrap last meaningful word in accent if short enough
    words = title.strip().split()
    if locale == "zh":
        return f"<h1>{html.escape(title)}</h1>"
    if len(words) >= 2:
        head = html.escape(" ".join(words[:-1]))
        tail = html.escape(words[-1])
        return f'<h1>{head} <span class="accent">{tail}</span></h1>'
    return f"<h1>{html.escape(title)}</h1>"


def insert_index_entry(index_path: str, entry_line: str) -> bool:
    txt = open(index_path, encoding="utf-8").read()
    m = re.search(r"path:\s*'([^']+)'", entry_line)
    if m and m.group(1) in txt:
        return False
    new_txt, n = re.subn(
        r"(const posts = \[\n)",
        r"\1" + entry_line + "\n",
        txt,
        count=1,
    )
    if n == 0:
        raise RuntimeError(f"cannot find posts array in {index_path}")
    open(index_path, "w", encoding="utf-8").write(new_txt)
    return True


def publish_post(rewritten: dict, meta: dict) -> str:
    slug = rewritten["slug"]
    # ensure unique
    if os.path.isfile(os.path.join(EN_BLOG, f"{slug}.astro")):
        slug = slugify(rewritten.get("title_en") or slug, prefix="wx-")
        rewritten["slug"] = slug

    cat = rewritten.get("category") or "Analysis"
    cat_en, cat_zh = CAT_MAP.get(cat, ("Analysis", "分析"))
    today = date.today()
    date_en = today.strftime("%B %d, %Y")
    date_zh = f"{today.year}年{today.month}月{today.day}日"
    source_url = meta.get("final_url") or meta.get("href") or ""

    en_body = rewritten["body_en_html"]
    zh_body = rewritten["body_zh_html"]
    # Strip accidental img tags from LLM
    en_body = re.sub(r"<img\b[^>]*>", "", en_body, flags=re.I)
    zh_body = re.sub(r"<img\b[^>]*>", "", zh_body, flags=re.I)

    en_astro = render_astro(
        "en", slug, cat_en,
        rewritten["title_en"], rewritten["desc_en"],
        accent_h1(rewritten["title_en"], "en"),
        date_en,
        rewritten.get("source_note_en") or "Rewritten from a WeChat clue for dshbase readers.",
        source_url,
        en_body,
    )
    zh_astro = render_astro(
        "zh", slug, cat_zh,
        rewritten["title_zh"], rewritten["desc_zh"],
        accent_h1(rewritten["title_zh"], "zh"),
        date_zh,
        rewritten.get("source_note_zh") or "改写自微信公众号线索，面向 dshbase 读者。",
        source_url,
        zh_body,
    )

    open(os.path.join(EN_BLOG, f"{slug}.astro"), "w", encoding="utf-8").write(en_astro)
    open(os.path.join(ZH_BLOG, f"{slug}.astro"), "w", encoding="utf-8").write(zh_astro)

    # blog-posts.json
    posts = load_json(BLOG_POSTS, [])
    path = f"/blog/{slug}/"
    if not any(p.get("path") == path for p in posts):
        posts.insert(
            0,
            {
                "path": path,
                "cat": cat_en,
                "cat_zh": cat_zh,
                "en": rewritten["title_en"],
                "zh": rewritten["title_zh"],
                "desc_en": rewritten["desc_en"],
                "desc_zh": rewritten["desc_zh"],
            },
        )
        save_json(BLOG_POSTS, posts)

    en_line = (
        f"  {{ path: '{path}', cat: '{cat_en}', "
        f"en: {json.dumps(rewritten['title_en'], ensure_ascii=False)}, "
        f"zh: {json.dumps(rewritten['title_zh'], ensure_ascii=False)}, "
        f"desc_en: {json.dumps(rewritten['desc_en'], ensure_ascii=False)}, "
        f"desc_zh: {json.dumps(rewritten['desc_zh'], ensure_ascii=False)} }},"
    )
    zh_line = (
        f"  {{ path: '{path}', cat: '{cat_zh}', "
        f"zh: {json.dumps(rewritten['title_zh'], ensure_ascii=False)}, "
        f"desc_zh: {json.dumps(rewritten['desc_zh'], ensure_ascii=False)} }},"
    )
    insert_index_entry(EN_INDEX, en_line)
    insert_index_entry(ZH_INDEX, zh_line)
    return slug


def main() -> int:
    ap = argparse.ArgumentParser(description="Weixin/Sogou → rewritten dshbase blog ingest")
    ap.add_argument("--search-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="search+fetch+rewrite but do not write files")
    ap.add_argument("--publish", action="store_true", help="write Astro + indexes")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--query", action="append", default=None, help="extra/override query (repeatable)")
    ap.add_argument("--http-fallback", action="store_true", help="try HTTP if bsk unavailable")
    ap.add_argument("--href", action="append", default=None, help="skip search; fetch these sogou/weixin URLs")
    ap.add_argument("--min-score", type=float, default=1.5)
    args = ap.parse_args()

    if not (args.search_only or args.dry_run or args.publish or args.href):
        ap.print_help()
        log("\n默认请显式指定 --search-only / --dry-run / --publish")
        return 2

    queries = args.query or DEFAULT_QUERIES
    state = load_state()
    titles = existing_blog_titles()

    candidates: list[dict] = []
    if args.href:
        for h in args.href:
            candidates.append({
                "title": "",
                "href": h,
                "account": "",
                "snippet": "",
                "query": "(manual)",
                "score": 3.0,
            })
    else:
        log("== search ==")
        if bsk_available():
            log("using bsk")
            candidates = search_sogou_bsk(queries)
        elif args.http_fallback:
            log("bsk unavailable — HTTP fallback (fragile)")
            candidates = search_sogou_http(queries)
        else:
            log("ERROR: bsk 不可用。安装/连接 browser-skill 后重试，或加 --http-fallback")
            return 1

    # filter + sort
    filtered = []
    for it in candidates:
        sc = it.get("score")
        if sc is None:
            it["score"] = score_item(it)
            sc = it["score"]
        if sc < args.min_score and not args.href:
            continue
        reason = is_duplicate(it, state, titles)
        if reason:
            it["skip_reason"] = reason
            continue
        filtered.append(it)
    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

    log(f"candidates: {len(candidates)} raw → {len(filtered)} after filter")
    for it in filtered[:20]:
        log(f"  [{it.get('score',0):.1f}] {it.get('title','')[:70]} | {it.get('account','')}")

    if args.search_only:
        out = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "candidates": filtered[:50],
        }
        dump = os.path.join(ROOT, "scripts", "_weixin_candidates.json")
        # don't leave _tmp in repo root; scripts/_weixin is ok but user said no _tmp_*
        save_json(dump, out)
        log(f"wrote {dump}")
        return 0

    # mark seen for all considered
    published_slugs = []
    to_process = filtered[: max(1, args.limit)]

    for i, it in enumerate(to_process):
        log(f"\n== [{i+1}/{len(to_process)}] fetch {it.get('title') or it.get('href')} ==")
        if not bsk_available() and not args.http_fallback:
            log("skip fetch: no bsk")
            continue
        if bsk_available():
            art = fetch_article_bsk(it["href"])
        else:
            log("HTTP article fetch not implemented (need bsk for mp.weixin)")
            continue

        if art.get("blocked") or art.get("textLen", 0) < 200:
            log(f"  blocked/captcha or too short (len={art.get('textLen')})")
            state["seen"].append({
                "title": it.get("title") or art.get("title"),
                "href": it.get("href"),
                "status": "blocked",
                "at": datetime.now(timezone.utc).isoformat(),
            })
            continue

        meta = {
            **it,
            "title": art.get("title") or it.get("title"),
            "account": art.get("account") or it.get("account"),
            "final_url": art.get("url") or it.get("href"),
        }
        # re-check covered themes on real title
        dup = is_duplicate({"title": meta["title"], "href": meta["final_url"]}, state, titles)
        if dup and dup.startswith("covered"):
            log(f"  skip covered theme: {dup}")
            state["seen"].append({**meta, "status": "covered", "at": datetime.now(timezone.utc).isoformat()})
            continue

        log(f"  rewriting ({art.get('textLen')} chars source)…")
        rewritten = rewrite_article(meta, art.get("text") or "")
        if not rewritten:
            log("  rewrite failed")
            continue
        if rewritten.get("skip"):
            log(f"  LLM skip: {rewritten.get('reason')}")
            state["seen"].append({
                "title": meta["title"],
                "href": meta.get("final_url") or meta.get("href"),
                "status": "llm-skip",
                "reason": rewritten.get("reason"),
                "at": datetime.now(timezone.utc).isoformat(),
            })
            continue

        if args.dry_run or not args.publish:
            log(f"  DRY-RUN ok → would publish slug={rewritten.get('slug')} title_zh={rewritten.get('title_zh')}")
            preview = os.path.join(ROOT, "scripts", f"_weixin_preview_{rewritten.get('slug','x')}.json")
            save_json(preview, {"meta": meta, "rewrite": rewritten})
            state["seen"].append({
                "title": meta["title"],
                "href": meta.get("final_url") or meta.get("href"),
                "status": "dry-run",
                "slug": rewritten.get("slug"),
                "at": datetime.now(timezone.utc).isoformat(),
            })
            continue

        slug = publish_post(rewritten, meta)
        published_slugs.append(slug)
        log(f"  published /blog/{slug}/")
        state["published"].append({
            "title": meta["title"],
            "href": meta.get("final_url") or meta.get("href"),
            "slug": slug,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        state["seen"].append({
            "title": meta["title"],
            "href": meta.get("final_url") or meta.get("href"),
            "status": "published",
            "slug": slug,
            "at": datetime.now(timezone.utc).isoformat(),
        })

    # prune state length
    state["seen"] = state["seen"][-500:]
    state["published"] = state["published"][-200:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_json(STATE_PATH, state)

    if published_slugs:
        try:
            subprocess.run(
                [sys.executable, os.path.join(ROOT, "scripts", "gen-sitemap.py")],
                cwd=ROOT,
                check=False,
            )
        except Exception as e:
            log(f"sitemap warn: {e}")

    log("\n== done ==")
    log(f"published: {published_slugs or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
