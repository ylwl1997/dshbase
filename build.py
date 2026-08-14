#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dshbase build.py — 把共享 nav/footer 模板注入每个页面。"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
TPL = ROOT / "templates"
NAV = (TPL / "nav.html").read_text(encoding="utf-8").strip()
FOOT = (TPL / "footer.html").read_text(encoding="utf-8").strip()
NAV_RE = re.compile(r'<header class="top">.*?</header>', re.S)
FOOT_RE = re.compile(r'<footer class="foot">.*?</footer>', re.S)
EXCLUDE = {"templates", "node_modules", "functions", "research", "test-files"}


def pages():
    for p in ROOT.rglob("index.html"):
        rel = p.relative_to(ROOT).parts[:-1]
        if any(part in EXCLUDE for part in rel):
            continue
        yield p


def main():
    built = changed = 0
    for p in sorted(pages()):
        html = p.read_text(encoding="utf-8")
        new = NAV_RE.sub(lambda m: NAV, html)
        new = FOOT_RE.sub(lambda m: FOOT, new)
        if new != html:
            p.write_text(new, encoding="utf-8")
            changed += 1
        built += 1
    print(f"built {built} pages, {changed} changed")


if __name__ == "__main__":
    main()
