#!/usr/bin/env python3
"""批量把英文 desc_zh 翻译成中文（DeepSeek）。"""
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

def translate_batch(descs):
    prompt = (
        "把下面每个英文插件描述翻译成简洁中文（每条 ≤30 字，保留插件名/技术名词）。"
        "返回 JSON 对象，格式 {\"zh\": [\"翻译1\", \"翻译2\", ...]}，顺序一一对应：\n\n"
        + "\n".join(f"{i+1}. {d}" for i, d in enumerate(descs))
    )
    for attempt in range(3):
        try:
            content = llm(prompt)
            obj = json.loads(content)
            zh = obj.get("zh", [])
            if len(zh) == len(descs):
                return zh
        except Exception as e:
            print("  重试:", e)
        time.sleep(2)
    return None

def main():
    d = json.load(open(DATA, encoding="utf-8"))
    allp = [p for items in d.values() for p in items]
    targets = [p for p in allp if p.get("desc_en") and (p.get("desc_zh") or "") == (p.get("desc_en") or "")]
    print(f"需要翻译的插件: {len(targets)}")

    BATCH = 30
    done = 0
    for i in range(0, len(targets), BATCH):
        batch = targets[i:i+BATCH]
        descs = [p["desc_en"] for p in batch]
        zh = translate_batch(descs)
        if zh:
            for p, z in zip(batch, zh):
                p["desc_zh"] = z
            done += len(batch)
            print(f"  批次 {i//BATCH+1}: 完成 {done}/{len(targets)}")
        else:
            print(f"  批次 {i//BATCH+1}: 失败，跳过")
        time.sleep(0.5)

    json.dump(d, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成，共翻译 {done} 个插件")

if __name__ == "__main__":
    main()
