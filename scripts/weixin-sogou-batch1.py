#!/usr/bin/env python3
"""One-shot first batch: rewrite 3 WeChat/Sogou themes into wx-* posts (no verbatim copy)."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

# Import helpers from ingest module
import importlib.util

spec = importlib.util.spec_from_file_location(
    "weixin_sogou_ingest",
    os.path.join(ROOT, "scripts", "weixin-sogou-ingest.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def read_dsk() -> str:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"].strip()
    cred = os.path.expanduser("~/.dsh/.credentials.yaml")
    txt = open(cred, encoding="utf-8").read()
    return re.search(r"DEEPSEEK_API_KEY:\s*(\S+)", txt).group(1).strip()


def llm(prompt: str) -> dict:
    data = json.dumps(
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.45,
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


BATCH = [
    {
        "slug": "wx-rc8-multimodal",
        "cat": "Guide",
        "title_hint_zh": "rc.8 多模态与子代理",
        "clue": "Sogou WeChat theme: DeepSeek Harness v0.1.0-rc.8; public mirrors: GitHub release + industry coverage",
        "source": "https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.0-rc.8",
        "facts": """rc.8 for installers:
- Native image requests configurable on DeepSeek adapters; /goal /plan accept images; @ menu file/session refs
- Claude Code + Codex as Profile Bundle subagents; Codex non-interactive + named instances
- Windows PTY persistent PowerShell (Minimal default)
- Fixes: large/many images; streaming cancel prefix; custom OpenAI-compatible gateways
- Tool-layer vision (OCR/pixels) still useful for text-only models; packs: modlens, dsh-vision-toolkit
- dshbase: verify installs; catalog may lag marketing claims""",
    },
    {
        "slug": "wx-orange-book-notes",
        "cat": "Analysis",
        "title_hint_zh": "橙皮书式拆解：安装者视角",
        "clue": "Sogou WeChat theme: 全拆解 / orange-book style teardown of DeepSeek Harness",
        "source": "https://github.com/alchaincyf/deepseek-harness-orange-book",
        "facts": """Installer field notes (do not paste book body):
- Subject shift: official docs say \"it\"; field notes say \"I\" after install
- dsh --profile web --dump-default-config / dump-config matter
- Append-only session logs across modes are the audit trail
- Create mode can invent tools — supply-chain risk
- PTC is not automatically cheaper; measure tokens/cache
- Packages on npm outside default closure — listed != installed
- dshbase verified directory + audit > star counts""",
    },
    {
        "slug": "wx-dsh-command-map",
        "cat": "Guide",
        "title_hint_zh": "dsh 常用命令地图",
        "clue": "Sogou WeChat theme: DeepSeek Harness 命令大全 — rewrite as practical map",
        "source": "https://weixin.sogou.com/weixin?type=2&query=DeepSeek+Harness+%E5%91%BD%E4%BB%A4",
        "facts": """Practical map (rc.x may change; verify docs):
- dsh web → ~127.0.0.1:3080
- --profile web --dump-config / --dump-default-config
- Modes Standard / PTC / Minimal / Create
- plugin add: npm | github:owner/repo | ./path
- Permissions Read Only / Workspace Write / Full Access
- rc.8 subagent bundles Claude Code & Codex
- Link dshbase modes/cost/sandbox/directory guides
- WeChat command lists go stale fast""",
    },
]


def main() -> int:
    results = []
    for b in BATCH:
        print("rewriting", b["slug"], flush=True)
        prompt = f"""你是 dshbase 编辑。根据线索写完全改写的双语博客 JSON。禁止照抄任何来源长句。面向安装者，少营销。
线索: {b['clue']}
事实要点: {b['facts']}
参考链: {b['source']}
建议 slug: {b['slug']}
分类: {b['cat']}
中文主题提示: {b['title_hint_zh']}

返回 JSON:
{{
  "slug": "{b['slug']}",
  "category": "{b['cat']}",
  "title_en": "...",
  "title_zh": "...",
  "desc_en": "<=160 chars",
  "desc_zh": "<=80字",
  "body_en_html": "only h2/p/ul/li/strong/code/pre/a",
  "body_zh_html": "同上",
  "source_note_en": "short credit that this is a rewrite from WeChat/Sogou clues + public release notes",
  "source_note_zh": "说明：改写自搜狗微信线索与公开发布说明，非原文搬运"
}}
"""
        obj = llm(prompt)
        obj["slug"] = b["slug"]
        obj["category"] = b["cat"]
        meta = {
            "title": obj.get("title_zh") or b["title_hint_zh"],
            "href": b["source"],
            "final_url": b["source"],
            "account": "WeChat/Sogou clue",
            "query": "DeepSeek Harness",
        }
        slug = mod.publish_post(obj, meta)
        print(" published", slug, flush=True)
        results.append({"slug": slug, "title_zh": obj.get("title_zh"), "source": b["source"]})

    state = mod.load_state()
    for r in results:
        state["published"].append(
            {
                "title": r["title_zh"],
                "href": r["source"],
                "slug": r["slug"],
                "at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                "batch": "manual-first",
            }
        )
        state["seen"].append(
            {
                "title": r["title_zh"],
                "href": r["source"],
                "status": "published",
                "slug": r["slug"],
                "at": state["published"][-1]["at"],
            }
        )
    state["updated_at"] = state["published"][-1]["at"]
    mod.save_json(mod.STATE_PATH, state)

    import subprocess

    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gen-sitemap.py")], cwd=ROOT)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
