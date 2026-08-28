# -*- coding: utf-8 -*-
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")

REMOTE = r'''
# -*- coding: utf-8 -*-
SW = "/tmp/k72_doc_extract/7-JLK1263C_JLK1263N型GLink高速光纤总线节点电路软件设计指南V1.6_公开_.pdf.txt"
HW = "/tmp/k72_doc_extract/6-JLK1263C_JLK1263N型GLink高速光纤总线节点电路硬件设计指南V2.0_公开_.pdf.txt"
with open(SW, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

ranges = [
    (1950, 2350, "SmartNC status/timeout/config tables area"),
    (3900, 4100, "timeout/config regs detail"),
    (4180, 4350, "table near 54"),
    (8200, 8700, "6.5 SmartNC operations"),
    (8700, 9200, "table54 + send format + init"),
    (9200, 9800, "SmartNT 6.6"),
    (2280, 2450, "SmartNT 0x3C area"),
]
out = open("/tmp/k72_doc_extract/smart_detail.txt", "w", encoding="utf-8")
for a,b,title in ranges:
    out.write("\n\n########## %s %d-%d ##########\n" % (title, a, b))
    out.write("".join(lines[a-1:b]))
out.close()
print("smart_detail written", sum(1 for _ in open("/tmp/k72_doc_extract/smart_detail.txt", encoding="utf-8")))

# HW pin mux FIFO SEL encoding block
with open(HW, encoding="utf-8", errors="replace") as f:
    hw = f.readlines()
with open("/tmp/k72_doc_extract/hw_fifo_sel.txt", "w", encoding="utf-8") as out:
    out.write("".join(hw[3280:3360]))
    out.write("\n----\n")
    out.write("".join(hw[3560:3680]))
    out.write("\n----\n")
    out.write("".join(hw[3710:3840]))
print("hw_fifo written")
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
with c.open_sftp().file("/tmp/dump_smart_detail.py", "w") as f:
    f.write(REMOTE)
stdin, stdout, stderr = c.exec_command("python3 /tmp/dump_smart_detail.py", timeout=30)
print(stdout.read().decode("utf-8", "replace"))
sftp = c.open_sftp()
sftp.get("/tmp/k72_doc_extract/smart_detail.txt", r"C:\Users\Administrator\dshbase\_tmp_smart_detail.txt")
sftp.get("/tmp/k72_doc_extract/hw_fifo_sel.txt", r"C:\Users\Administrator\dshbase\_tmp_hw_fifo_sel.txt")
sftp.get("/tmp/k72_doc_extract/smart_sections.txt", r"C:\Users\Administrator\dshbase\_tmp_smart_sections.txt")
sftp.close()
c.close()
print("ok")
