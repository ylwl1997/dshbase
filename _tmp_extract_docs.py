# -*- coding: utf-8 -*-
"""Extract Smart/FIFO related text from K72 Doc manuals."""
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")

REMOTE_SCRIPT = r'''
# -*- coding: utf-8 -*-
import os, sys, re, zipfile, subprocess

DOC = "/opt/soft/K72_GLink/Doc"
OUT = "/tmp/k72_doc_extract"
os.makedirs(OUT, exist_ok=True)

def try_imports():
    mods = {}
    for name in ("pypdf", "PyPDF2", "fitz", "pdfminer", "docx"):
        try:
            mods[name] = __import__(name)
            print("HAS", name)
        except Exception as e:
            print("NO", name, str(e)[:60])
    # pdftotext
    r = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)
    print("pdftotext:", r.stdout.strip() or "missing")
    return mods

mods = try_imports()

def extract_docx(path, out_txt):
    # docx is a zip; word/document.xml
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    text = re.sub(r"</w:p>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(text)
    print("DOCX ->", out_txt, "chars", len(text))
    return text

def extract_pdf_pdftotext(path, out_txt):
    r = subprocess.run(["pdftotext", "-layout", path, out_txt], capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(out_txt):
        n = os.path.getsize(out_txt)
        print("PDF pdftotext ->", out_txt, "bytes", n)
        return True
    print("pdftotext fail", r.stderr[:200])
    return False

def extract_pdf_pypdf(path, out_txt):
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception as e:
            print("no pypdf", e)
            return False
    reader = PdfReader(path)
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        parts.append(t)
    text = "\n".join(parts)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(text)
    print("PDF pypdf ->", out_txt, "pages", len(reader.pages), "chars", len(text))
    return True

# 1) FPGA register docx
docx = os.path.join(DOC, "glinkfpga寄存器说明.docx")
if os.path.exists(docx):
    extract_docx(docx, os.path.join(OUT, "fpga_regs.txt"))

# 2) key PDFs
pdfs = [
    "7-JLK1263C JLK1263N型GLink高速光纤总线节点电路软件设计指南V1.6（公开）.pdf",
    "6-JLK1263C JLK1263N型GLink高速光纤总线节点电路硬件设计指南V2.0（公开）.pdf",
    "3-JLK1263N型GLink高速光纤总线节点电路普通军用产品说明书_A2.pdf",
]
for name in pdfs:
    path = os.path.join(DOC, name)
    if not os.path.exists(path):
        print("missing", name)
        continue
    safe = re.sub(r"[^\w.-]+", "_", name)[:80]
    out = os.path.join(OUT, safe + ".txt")
    ok = False
    # prefer pdftotext
    r = subprocess.run(["which", "pdftotext"], capture_output=True)
    if r.returncode == 0:
        ok = extract_pdf_pdftotext(path, out)
    if not ok:
        ok = extract_pdf_pypdf(path, out)
    if not ok:
        print("FAILED", name)

print("DONE list:")
for f in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, f)
    print(f, os.path.getsize(p))
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
sftp = c.open_sftp()
with sftp.file("/tmp/extract_k72_docs.py", "w") as f:
    f.write(REMOTE_SCRIPT)
sftp.close()
stdin, stdout, stderr = c.exec_command("python3 /tmp/extract_k72_docs.py", timeout=300)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err:
    print("STDERR:", err[:3000])
c.close()
