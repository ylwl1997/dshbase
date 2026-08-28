#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
patterns = [
    'client_llm_gateway_credential', 'ClientLlmGatewayCredential',
    'LlmGatewaySettings', 'llm_gateway', 'customBaseUrl', 'baseUrl',
    'model-bindings.json', 'modelBindingsPath', 'readModelBindings',
    'opengrok', 'hopBaseUrl', 'provider-maps',
]
for pat in patterns:
    idx = text.find(pat)
    if idx < 0:
        print(pat, ': NOT FOUND')
        continue
    print(f'=== {pat} @ {idx} ===')
    print(text[max(0,idx-150):idx+400][:600])
    print()
"""
sftp = c.open_sftp()
with sftp.file("/tmp/grep_byok2.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/grep_byok2.py", timeout=60)
print(o.read().decode("utf-8", "replace")[:10000])
c.close()
