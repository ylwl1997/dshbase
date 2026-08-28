import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
sftp = client.open_sftp()
helper = r'''#!/usr/bin/env python3
import os,re

# Full SmartNCShortMsg.vhd state machine
p="/opt/soft/Driver/GLink/Doc/GLink高速光纤总线应用资料包/15.Glink高速光纤总线大数据NC用例及技术说明/JLK1263_SmartNCShortMsg_Demo/FPGA示例文件/SmartNCShortMsg.vhd"
t=open(p,encoding="utf-8",errors="replace").read()
print("===== SmartNCShortMsg.vhd len",len(t),"=====")
print(t)

print("\n\n===== DSP GLink.c NC demo (smart parts) =====")
p2="/opt/soft/Driver/GLink/Doc/GLink高速光纤总线应用资料包/15.Glink高速光纤总线大数据NC用例及技术说明/JLK1263_SmartNCShortMsg_Demo/DSP示例文件/GLink.c"
t2=open(p2,encoding="utf-8",errors="replace",errors="replace").read() if False else open(p2,encoding="utf-8",errors="replace").read()
# print functions mentioning Smart or FIFO or short
for m in re.finditer(r'(?s)^[^\n]*(Smart|SMART|短|FIFO|0x0C|WORK|NODE).{0,200}', t2):
  pass
# better: extract function bodies with Smart
lines=t2.splitlines()
for i,l in enumerate(lines):
  if re.search(r'Smart|SMARTNC|短报文|FIFO1|0x1000|trig|TRIG|配置', l, re.I):
    print(f"{i+1}: {l[:200]}")
print("--- file size", len(t2), "lines", len(lines))
# print first 200 lines and search Init
print("===== head =====")
print("\n".join(lines[:150]))
'''
# fix duplicate errors=
helper = helper.replace('encoding="utf-8",errors="replace",errors="replace"','encoding="utf-8",errors="replace"')
with sftp.file("/tmp/_nc_demo.py","w") as f:
    f.write(helper)
sftp.close()
stdin,stdout,stderr=client.exec_command("python3 /tmp/_nc_demo.py 2>&1", timeout=60)
out=stdout.read().decode("utf-8","replace")
open(r"C:\Users\Administrator\dshbase\_tmp_nc_demo.txt","w",encoding="utf-8").write(out)
print(out[:18000])
print("TOT", len(out))
client.close()
