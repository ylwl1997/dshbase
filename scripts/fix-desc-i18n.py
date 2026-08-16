#!/usr/bin/env python3
"""修复 desc 双语一致性：
  A. desc_en 为英文但 desc_zh 为空 -> 英译中，补齐中文站。
  B. desc_en 为中文但 desc_zh 为空 -> 直接把中文抄进 desc_zh（免翻译）。
  C. desc_en 被中文污染 -> 中译英，回写 desc_en 和 desc（修复英文站显示中文）。

用法：python scripts/fix-desc-i18n.py
"""
import json
import os
import re
import time
import urllib.request

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "data", "plugins.json"))


def read_dsk():
    txt = open(os.path.expanduser("~/.dsh/.credentials.yaml"), encoding="utf-8").read()
    return re.search(r"DEEPSEEK_API_KEY:\s*(\S+)", txt).group(1)


def llm(prompt):
    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=data, headers={
        "Authorization": "Bearer " + read_dsk(),
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def translate_batch(texts, direction):
    if direction == "zh":
        prompt = ("把下面每个英文插件描述翻译成简洁中文（每条 ≤30 字，保留插件名/技术名词）。"
                  "返回 JSON 对象，格式 {\"out\": [\"翻译1\", \"翻译2\", ...]}，顺序一一对应：\n\n"
                  + "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts)))
    else:
        prompt = ("把下面每个中文插件描述翻译成简洁英文（保留插件名/技术名词）。"
                  "返回 JSON 对象，格式 {\"out\": [\"translation1\", \"translation2\", ...]}，顺序一一对应：\n\n"
                  + "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts)))
    for attempt in range(3):
        try:
            obj = json.loads(llm(prompt))
            out = obj.get("out", [])
            if len(out) == len(texts):
                return out
        except Exception as e:
            print("  重试:", e)
        time.sleep(2)
    return None


def clean(s):
    return (s or "").encode("utf-8", "ignore").decode("utf-8") if s else ""


def cjk(s):
    return bool(re.search(r"[一-鿿]", clean(s)))


def run_batches(targets, direction, key_out, key_src):
    BATCH = 30
    done = 0
    total = len(targets)
    for i in range(0, total, BATCH):
        b = targets[i:i + BATCH]
        texts = [p[key_src] for p in b]
        out = translate_batch(texts, direction)
        if out:
            for p, t in zip(b, out):
                p[key_out] = t
            done += len(b)
        print(f"  批次 {i // BATCH + 1}/{(total + BATCH - 1) // BATCH}: {done}/{total}")
        time.sleep(0.5)


def main():
    d = json.load(open(DATA, encoding="utf-8"))
    allp = [p for items in d.values() for p in items]

    # B) desc_en 中文 + desc_zh 空 -> 抄
    copied = 0
    for p in allp:
        den = (p.get("desc_en") or "").strip()
        if den and cjk(den) and not (p.get("desc_zh") or "").strip():
            p["desc_zh"] = den
            copied += 1
    print(f"[B] 抄中文 desc_en -> desc_zh: {copied}")

    # A) desc_en 英文 + desc_zh 空 -> 英译中
    a = [p for p in allp if (p.get("desc_en") or "").strip() and not cjk(p.get("desc_en")) and not (p.get("desc_zh") or "").strip()]
    print(f"[A] 英译中: {len(a)}")
    run_batches(a, "zh", "desc_zh", "desc_en")

    # C) desc_en 中文 -> 中译英（回写 desc_en + desc）
    c = [p for p in allp if (p.get("desc_en") or "").strip() and cjk(p.get("desc_en"))]
    print(f"[C] 中译英: {len(c)}")
    run_batches(c, "en", "desc_en", "desc_en")
    for p in c:
        p["desc"] = p.get("desc_en") or p.get("desc")

    json.dump(d, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("完成，已写回 plugins.json")


if __name__ == "__main__":
    main()
