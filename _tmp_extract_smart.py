# -*- coding: utf-8 -*-
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")

REMOTE = r'''
# -*- coding: utf-8 -*-
import os, re

SW = "/tmp/k72_doc_extract/7-JLK1263C_JLK1263N型GLink高速光纤总线节点电路软件设计指南V1.6_公开_.pdf.txt"
HW = "/tmp/k72_doc_extract/6-JLK1263C_JLK1263N型GLink高速光纤总线节点电路硬件设计指南V2.0_公开_.pdf.txt"

with open(SW, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

def find_line(pat, start=0):
    for i in range(start, len(lines)):
        if re.search(pat, lines[i]):
            return i
    return -1

# Find key section starts by unique headings (body, not TOC - look for page markers nearby)
keys = [
    (r"^\\s*5\\.2\\.11\\s+SmartNC", "5.2.11 SmartNC regs"),
    (r"^\\s*5\\.2\\.12\\s+SmartNT", "5.2.12 SmartNT regs"),
    (r"SmartNC 超时|超时设置寄存器", "timeout"),
    (r"SmartNC 配置寄存器|配置寄存器.*短报文", "config"),
    (r"表\\s*5[0-9].*短|表\\s*54|短报文.*格式|发送数据格式", "table54-ish"),
    (r"^\\s*6\\.5\\s+SmartNC", "6.5 SmartNC ops"),
    (r"6\\.5\\.2|长/短报文工作模式", "6.5.2 modes"),
    (r"6\\.5\\.[0-9].*软件|初始化流程|发送流程|接收流程", "6.5 flow"),
    (r"SmartNT.*配置|0x3C|REG\\(0x3C\\)", "SmartNT 0x3C"),
    (r"FIFO_WR_SEL|FIFO_RD_SEL|写选择|读选择", "FIFO SEL"),
    (r"bit\\[7:4\\]|失败计数|交换组忙|单交换忙", "status bits"),
]

print("=== LINE INDEX ===")
for pat, name in keys:
    idxs = [i for i,l in enumerate(lines) if re.search(pat, l)]
    print(name, "->", [i+1 for i in idxs[:8]], "count", len(idxs))

# Dump large chunks around SmartNC register definitions and 6.5
chunks = []
# find body 5.2.11 - usually after "第 xx 页" and not in TOC. TOC has dots.
for i,l in enumerate(lines):
    if re.search(r"5\\.2\\.11\\s+SmartNC 相关寄存器", l) and "...." not in l and i > 800:
        chunks.append(("5.2.11@%d" % (i+1), i, i+250))
        break
for i,l in enumerate(lines):
    if re.search(r"5\\.2\\.12\\s+SmartNT 相关寄存器", l) and "...." not in l and i > 800:
        chunks.append(("5.2.12@%d" % (i+1), i, i+120))
        break
for i,l in enumerate(lines):
    if re.search(r"6\\.5\\s+SmartNC 操作", l) and "...." not in l and i > 2000:
        chunks.append(("6.5@%d" % (i+1), i, i+400))
        break
for i,l in enumerate(lines):
    if re.search(r"6\\.6\\s+SmartNT", l) and "...." not in l and i > 2000:
        chunks.append(("6.6@%d" % (i+1), i, i+200))
        break
for i,l in enumerate(lines):
    if "表 54" in l or "表54" in l:
        chunks.append(("表54@%d" % (i+1), max(0,i-5), i+80))
for i,l in enumerate(lines):
    if re.search(r"工作模式配置寄存器", l) and "...." not in l and i > 800 and "5.2.3" in lines[max(0,i-3):i+1][0] if False else True:
        if "5.2.3" in l and i > 900:
            chunks.append(("5.2.3@%d" % (i+1), i, i+80))
            break

# Better search for table 54 content about short message format
for i,l in enumerate(lines):
    if re.search(r"子地址|偏移地址.*长度|NT_ID.*Type|重传使能", l) and i > 3000:
        # check nearby for Smart
        ctx = "".join(lines[max(0,i-20):i+5])
        if "Smart" in ctx or "短报" in ctx or "表" in ctx:
            chunks.append(("fmt@%d" % (i+1), max(0,i-30), i+60))
            if len([c for c in chunks if c[0].startswith("fmt")]) >= 3:
                break

out_path = "/tmp/k72_doc_extract/smart_sections.txt"
with open(out_path, "w", encoding="utf-8") as out:
    for title, a, b in chunks:
        out.write("\n\n########## %s lines %d-%d ##########\n" % (title, a+1, b))
        out.write("".join(lines[a:b]))
print("wrote", out_path, "chunks", len(chunks))
for title,a,b in chunks:
    print(title, a+1, b)

# Also search HW for FIFO_WR_SEL encoding
with open(HW, encoding="utf-8", errors="replace") as f:
    hw = f.readlines()
print("\n=== HW FIFO SEL ===")
for i,l in enumerate(hw):
    if re.search(r"FIFO_WR_SEL|FIFO_RD_SEL|SmartNC1|00：|01：|10：|11：", l):
        if i > 200:  # skip toc-ish
            print("%d: %s" % (i+1, l.rstrip()[:120]))
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
with c.open_sftp().file("/tmp/extract_smart_sec.py", "w") as f:
    f.write(REMOTE)
stdin, stdout, stderr = c.exec_command("python3 /tmp/extract_smart_sec.py 2>&1", timeout=60)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:1000])
# download smart sections
sftp = c.open_sftp()
sftp.get("/tmp/k72_doc_extract/smart_sections.txt", r"C:\Users\Administrator\dshbase\_tmp_smart_sections.txt")
sftp.close()
c.close()
print("downloaded")
