#!/usr/bin/env python3
"""Map sand-host inference entry points for a bindings hook."""
import paramiko
from pathlib import Path

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    "64.83.13.119",
    port=22022,
    username="box",
    password="PBkNIKuNgv3OrOTMTiPK",
    timeout=15,
    allow_agent=False,
    look_for_keys=False,
)

remote = r"""
text = open('/home/box/sand-host/host-main.cjs', encoding='utf-8', errors='replace').read()
anchors = [
    'createCursorSandInference',
    'createSession(',
    'resolveSandRequestedModel',
    'createCursorInferencePromptSession',
    'SAND_INFERENCE_PROVIDER',
    'createXaiPromptSession',
    'openai-compatible',
    'chat/completions',
    'baseURL',
    'baseUrl',
    'RequestedModel',
    'client_llm_gateway_credential',
]
for a in anchors:
    idx = text.find(a)
    print(f'=== {a} @ {idx} ===')
    if idx < 0:
        continue
    print(text[max(0, idx-120):idx+900])
    print()

# find createSession body near createCursorSandInference
idx = text.find('createCursorSandInference')
# search forward for return createSession or createCursorInferencePromptSession
for key in ['createCursorInferencePromptSession', 'resolveSandRequestedModel(', 'createSession(']:
    j = text.find(key, idx)
    print(f'after createCursorSandInference: {key} @ {j} delta={j-idx if j>=0 else None}')
    if j >= 0:
        print(text[j:j+1200])
        print('---')
"""
sftp = c.open_sftp()
with sftp.file("/tmp/map_inference.py", "w") as f:
    f.write(remote)
sftp.close()
_, o, e = c.exec_command("python3 /tmp/map_inference.py", timeout=90)
out = (o.read() + e.read()).decode("utf-8", "replace")
Path(r"C:\Users\Administrator\dshbase\_tmp_map_inference.txt").write_text(out, encoding="utf-8")
print("wrote", len(out), "chars")
c.close()
