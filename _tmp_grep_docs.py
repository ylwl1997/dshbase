# -*- coding: utf-8 -*-
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")

REMOTE = r'''
# -*- coding: utf-8 -*-
import os, re

OUT = "/tmp/k72_doc_extract"
SW = os.path.join(OUT, "7-JLK1263C_JLK1263N型GLink高速光纤总线节点电路软件设计指南V1.6_公开_.pdf.txt")
HW = os.path.join(OUT, "6-JLK1263C_JLK1263N型GLink高速光纤总线节点电路硬件设计指南V2.0_公开_.pdf.txt")
FPGA = os.path.join(OUT, "fpga_regs.txt")
PROD = os.path.join(OUT, "3-JLK1263N型GLink高速光纤总线节点电路普通军用产品说明书_A2.pdf.txt")

def grep_ctx(path, patterns, window=3, max_hits=40):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print("\n========", os.path.basename(path), "lines", len(lines), "========")
    hits = 0
    for i, line in enumerate(lines):
        if any(re.search(p, line) for p in patterns):
            lo = max(0, i - window)
            hi = min(len(lines), i + window + 1)
            print(f"--- L{i+1} ---")
            for j in range(lo, hi):
                mark = ">>" if j == i else "  "
                print(f"{mark}{j+1}: {lines[j].rstrip()}")
            hits += 1
            if hits >= max_hits:
                print("... truncated hits ...")
                break
    print("total_hits_shown", hits)

# FPGA regs full
print("===== FULL FPGA REGS DOCX =====")
print(open(FPGA, encoding="utf-8", errors="replace").read())

# Software guide: Smart sections
grep_ctx(SW, [
    r"SmartNC|SmartNT|smartNC|smartNT|短报文|短消息|表\s*54|表54",
    r"0x2A|0x29|0x3C|FIFO_WR|FIFO_RD|WR_SEL|RD_SEL",
], window=2, max_hits=50)

# More specific chapter search
grep_ctx(SW, [
    r"5\.2\.|6\.5|大数据|配置寄存器|状态寄存器|超时",
], window=1, max_hits=30)

# Hardware: SSC_CLK, FIFO select
grep_ctx(HW, [
    r"Smart|FIFO|I_SSC_CLK|WR_SEL|RD_SEL|短报文|TRIG",
], window=2, max_hits=40)

# Product manual smart
grep_ctx(PROD, [
    r"Smart|短报文|大数据",
], window=2, max_hits=20)
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
with c.open_sftp().file("/tmp/grep_k72_docs.py", "w") as f:
    f.write(REMOTE)
stdin, stdout, stderr = c.exec_command("python3 /tmp/grep_k72_docs.py 2>&1", timeout=120)
out = stdout.read().decode("utf-8", "replace")
# save locally too
open(r"C:\Users\Administrator\dshbase\_tmp_doc_grep.txt", "w", encoding="utf-8").write(out)
print(out[:25000])
print("\n...[saved full to _tmp_doc_grep.txt, total chars", len(out), "]...")
c.close()
