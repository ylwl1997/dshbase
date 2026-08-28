#!/usr/bin/env python3
import json
import paramiko
from pathlib import Path

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
import json, glob, re
files = glob.glob('/home/box/sand-data/agent-transcripts/**/*.jsonl', recursive=True)
for fp in sorted(files, key=lambda x: -len(open(x,'rb').read()))[:6]:
    print('FILE', fp)
    with open(fp, encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f):
            if any(k in line.lower() for k in ['model', 'grok', 'qwen', 'routed', 'requestedmodel']):
                if i < 5 or 'model' in line.lower():
                    try:
                        d = json.loads(line)
                        s = json.dumps(d, ensure_ascii=False)[:400]
                    except Exception:
                        s = line[:400]
                    print(' ', i, s)
    print()
"""
sftp = c.open_sftp()
with sftp.file("/tmp/scan_transcripts.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/scan_transcripts.py", timeout=60)
out = o.read().decode("utf-8", "replace")[:8000]
Path(r"C:\Users\Administrator\dshbase\_tmp_transcript_scan.txt").write_text(out, encoding="utf-8")
print("wrote", len(out), "chars")
c.close()
