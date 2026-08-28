# -*- coding: utf-8 -*-
import paramiko
import sys
import os
import re

sys.stdout.reconfigure(encoding="utf-8")

REMOTE = r'''
# -*- coding: utf-8 -*-
import os, re, zipfile, subprocess

DOC = "/opt/soft/K72_GLink/Doc"
OUT = "/tmp/k72_smart_support"
os.makedirs(OUT, exist_ok=True)

# list all docs again with sizes
print("=== DOC TREE ===")
for root, dirs, files in os.walk(DOC):
    for f in files:
        p = os.path.join(root, f)
        print("%8d  %s" % (os.path.getsize(p), p.replace(DOC+"/", "")))

patterns = [
    r"Smart|SMART|智能|大数据|短报文|长报文",
    r"限制|不支持|暂不|仅支持|复用|FIFO|SSC_CLK|GC_MODE",
    r"CtrlNC|CtrlNT|控制流",
]

def extract_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    text = re.sub(r"</w:p>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", text)
    return text

def grep_file(path, label, max_hits=40):
    try:
        if path.endswith(".docx"):
            text = extract_docx(path)
            lines = text.splitlines()
        elif path.endswith((".md", ".txt", ".c", ".h", ".v", ".vhd")):
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        elif path.endswith(".pdf"):
            out = os.path.join(OUT, os.path.basename(path) + ".txt")
            if not os.path.exists(out) or os.path.getsize(out) < 100:
                subprocess.run(["pdftotext", "-layout", path, out], capture_output=True)
            if not os.path.exists(out):
                print("NOTEXT", path)
                return
            with open(out, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        else:
            return
    except Exception as e:
        print("ERR", path, e)
        return

    print("\n========", label, "lines", len(lines), "========")
    hits = 0
    for i, line in enumerate(lines):
        if re.search(r"Smart|SMART|智能NC|智能NT|大数据|短报文|长报文|不支持|限制|SSC_CLK|FIFO_WR_SEL|GC_MODE|工作模式", line, re.I):
            # skip pure TOC dots sometimes
            lo = max(0, i-1)
            hi = min(len(lines), i+2)
            print("--- L%d ---" % (i+1))
            for j in range(lo, hi):
                mark = ">>" if j == i else "  "
                print("%s%s" % (mark, lines[j].rstrip()[:160]))
            hits += 1
            if hits >= max_hits:
                print("...truncated...")
                break
    print("hits", hits)

# Priority K72-specific
cands = []
for root, dirs, files in os.walk(DOC):
    for f in files:
        p = os.path.join(root, f)
        low = f.lower()
        if any(x in low for x in ["k72", "glinkfpga", "工程", "api_demo", "原理", "寄存器"]):
            cands.append(p)
        if f.endswith((".md", ".docx")):
            cands.append(p)

# unique
seen = set()
for p in cands:
    if p in seen: continue
    seen.add(p)
    grep_file(p, p.replace(DOC+"/", ""), max_hits=30)

# Also search hardware guide V2.9 in DEMO if present (K72 datasheet folder)
v29 = None
for root, dirs, files in os.walk(DOC):
    for f in files:
        if "V2.9" in f or "硬件设计指南" in f:
            grep_file(os.path.join(root, f), "HW:"+f, max_hits=25)

# Search extracted software guide for K72 / 板级 / 限制 related to Smart dual role
sw = "/tmp/k72_doc_extract/7-JLK1263C_JLK1263N型GLink高速光纤总线节点电路软件设计指南V1.6_公开_.pdf.txt"
if os.path.exists(sw):
    print("\n=== SW guide: Smart limitations / 单板 / 同时 ===")
    with open(sw, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if re.search(r"同时使能|不能同时|互斥|限制|仅能|单板|自环|SmartNC.*SmartNT|工作模式.*Smart", line):
            print("%d: %s" % (i+1, line.rstrip()[:150]))
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
with c.open_sftp().file("/tmp/k72_smart_support.py", "w") as f:
    f.write(REMOTE)
stdin, stdout, stderr = c.exec_command("python3 /tmp/k72_smart_support.py 2>&1", timeout=180)
out = stdout.read().decode("utf-8", "replace")
open(r"C:\Users\Administrator\dshbase\_tmp_k72_smart_support.txt", "w", encoding="utf-8").write(out)
print(out[:35000])
print("\n... total", len(out), "chars saved ...")
c.close()
