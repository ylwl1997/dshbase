# -*- coding: utf-8 -*-
import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8")

REMOTE = r'''
# -*- coding: utf-8 -*-
import os, re, subprocess

OUT = "/tmp/k72_smart_support"
os.makedirs(OUT, exist_ok=True)

# Extract key sections from HW V2.9 and product manual about work mode / mux / restrictions
files = {
 "hw29": "/opt/soft/K72_GLink/Doc/DEMO/Glink-k72/Glink-k72/datasheet/【非密_V2.9发布】JLK1263型GLink高速光纤总线节点电路硬件设计指南_V2.9_1.pdf",
 "hw20": "/opt/soft/K72_GLink/Doc/6-JLK1263C JLK1263N型GLink高速光纤总线节点电路硬件设计指南V2.0（公开）.pdf",
 "prod": "/opt/soft/K72_GLink/Doc/3-JLK1263N型GLink高速光纤总线节点电路普通军用产品说明书_A2.pdf",
}
for k,p in files.items():
    out = os.path.join(OUT, k+".txt")
    if not os.path.exists(out) or os.path.getsize(out)<1000:
        subprocess.run(["pdftotext","-layout",p,out], capture_output=True)
    print(k, "bytes", os.path.getsize(out) if os.path.exists(out) else 0)

# Search work mode mutual exclusion, pin mux
for name in ["hw29","hw20","prod"]:
    path = os.path.join(OUT, name+".txt")
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    print("\n########", name, "key snippets ########")
    keys = [
        r"工作模式配置|互斥|不能同时|同时使能|复用|标准模式",
        r"SmartNC.*短|短报文|长报文",
        r"I_SSC_CLK|建议.*200|FIFO1.*共用",
        r"管脚复用|功能复用|NM_|监听",
        r"CtrlNC.*Smart|同时有",
    ]
    shown = 0
    for i,l in enumerate(lines):
        if any(re.search(p,l) for p in keys):
            if i < 200 and "...." in l:  # skip toc
                continue
            ctx = "".join(lines[max(0,i-1):min(len(lines),i+3)])
            if re.search(r"Smart|FIFO|SSC|复用|同时|互斥|标准模式|短报文|长报文", ctx):
                print("---%d---" % (i+1))
                print("".join(lines[max(0,i-1):min(len(lines),i+4)])[:500])
                shown += 1
                if shown >= 20:
                    break

# SW guide MODE register bits - can SmartNC and SmartNT enable together?
sw = "/tmp/k72_doc_extract/7-JLK1263C_JLK1263N型GLink高速光纤总线节点电路软件设计指南V1.6_公开_.pdf.txt"
print("\n######## SW 5.2.3 WORK_MODE ########")
with open(sw, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i,l in enumerate(lines):
    if re.search(r"5\\.2\\.3\\s+工作模式|工作模式配置寄存器", l) and "...." not in l and i>900:
        print("".join(lines[i:i+80]))
        break

# find "图 19" SmartNC and SmartNT same chip
print("\n######## 图19 / 同时使用 SmartNC+SmartNT ########")
for i,l in enumerate(lines):
    if "图 19" in l or "第 1 路 SmartNC 和第 1 路 SmartNT" in l:
        print("%d: %s" % (i+1, l.rstrip()[:120]))
        print("".join(lines[i:i+25])[:800])

# FPGA docx already known - print smart related full from extract
print("\n######## 工程使用说明 Smart coverage ########")
eng = open("/opt/soft/K72_GLink/Doc/工程使用说明.md", encoding="utf-8").read()
print("mentions Smart?", "Smart" in eng or "智能" in eng)
print("mentions Ctrl?", "Ctrl" in eng or "控制" in eng)
print("focus excerpt MODE line:")
for l in eng.splitlines():
    if "WORK_MODE" in l or "Smart" in l or "控制流" in l or "测试" in l[:5]:
        print(l)

# Check schematic net names count
sch = os.path.join(OUT, "sch.txt")
subprocess.run(["pdftotext","-layout",
 "/opt/soft/K72_GLink/Doc/DEMO/Glink-k72/Glink-k72/GLINK_K72原理图.pdf", sch], capture_output=True)
text = open(sch, encoding="utf-8", errors="replace").read()
for sig in ["SMARTNC1_TRIG","SMARTNC1_IDLE","SMARTNC1_EMPTY","SMARTNT1_ACK","SMARTNT1_REQ",
            "I_SSC_CLK","FIFO1_WR","FIFO1_RD","SMARTNC1","SMARTNT1"]:
    print("schematic", sig, "count", text.count(sig), "or", text.count("JLK_"+sig) if not sig.startswith("JLK") else "")
# count JLK_SMART*
import collections
names = re.findall(r"JLK_SMART[A-Z0-9_]+", text)
print("unique JLK_SMART* nets:", len(set(names)))
for n in sorted(set(names))[:40]:
    print(" ", n)
'''

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16",username="root",password="60851.org",timeout=20)
with c.open_sftp().file("/tmp/k72_smart2.py","w") as f: f.write(REMOTE)
stdin,stdout,stderr=c.exec_command("python3 /tmp/k72_smart2.py 2>&1", timeout=120)
out=stdout.read().decode("utf-8","replace")
open(r"C:\Users\Administrator\dshbase\_tmp_k72_smart2.txt","w",encoding="utf-8").write(out)
print(out[:28000])
c.close()
