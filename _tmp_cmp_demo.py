import paramiko, sys, os
sys.stdout.reconfigure(encoding="utf-8")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
sftp = client.open_sftp()

# list and fetch key demo files
base = "/opt/soft/Driver/GLink/Doc/GLink高速光纤总线应用资料包"
paths = []
stdin, stdout, stderr = client.exec_command(
    f"find '{base}/15.Glink高速光纤总线大数据NC用例及技术说明/JLK1263_SmartNCShortMsg_Demo' "
    f"'{base}/16.Glink高速光纤总线大数据NT用例及技术说明/JLK1263_SmartNTShortMsg_Demo' "
    f"-type f 2>/dev/null | head -80; "
    f"ls -la /root/glink_test/; wc -l /root/glink_test/jlk_smart_test.c",
    timeout=30,
)
print(stdout.read().decode("utf-8", "replace"))

# get C test and vhd snippets via remote python
helper = r'''#!/usr/bin/env python3
import os,re
# print jlk_smart_test.c fully or head
p="/root/glink_test/jlk_smart_test.c"
print("===== jlk_smart_test.c =====")
print(open(p,encoding="utf-8",errors="replace").read()[:20000])

# SmartNCShortMsg.vhd key process
for root,ds,fs in os.walk("/opt/soft/Driver/GLink/Doc"):
  for f in fs:
    if f in ("SmartNCShortMsg.vhd","SmartNTShortMsg.vhd"):
      path=os.path.join(root,f)
      print("===== ",path," =====")
      t=open(path,encoding="utf-8",errors="replace").read()
      print(t[:12000])
      print("----- hits -----")
      for i,l in enumerate(t.splitlines()):
        if re.search(r"TRIG|WDATA|WR_SEL|SSC|短|offset|0x|FIFO", l, re.I):
          if i<400 or "TRIG" in l.upper() or "WDATA" in l.upper():
            print(f"{i+1}: {l[:160]}")
'''
with sftp.file("/tmp/_cmp_demo.py","w") as f:
    f.write(helper)
sftp.close()
stdin,stdout,stderr=client.exec_command("python3 /tmp/_cmp_demo.py 2>&1", timeout=60)
out=stdout.read().decode("utf-8","replace")
# save locally for reading
open(r"C:\Users\Administrator\dshbase\_tmp_demo_out.txt","w",encoding="utf-8").write(out)
print(out[:15000])
print("... total", len(out))
client.close()
