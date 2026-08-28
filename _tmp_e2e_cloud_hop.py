#!/usr/bin/env python3
"""E2E: sendPrompt via sand gateway, verify hop log shows qwen traffic."""
import json
import time
import uuid
import paramiko
from pathlib import Path

HOST = "64.83.13.119"
PORT = 22022
USER = "box"
PASSWORD = "PBkNIKuNgv3OrOTMTiPK"
AGENT_ID = "a67d15ec-b377-46ba-b6f3-182a0982f683"  # yest -> qwen3.6-flash
PROMPT = "Reply with exactly one line: QWEN_ROUTE_TEST_OK. Do not use tools."
LOG = "/home/box/opengrok/token-plan-hop.log"
OUT = Path(r"C:\Users\Administrator\dshbase\_tmp_e2e_hop_result.txt")


def run(client, cmd, timeout=120):
    _, o, e = client.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main():
    lines = []
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD,
              timeout=20, allow_agent=False, look_for_keys=False)

    gw = json.loads(run(c, "cat /home/box/sand-data/gateway.json", 10))
    token = gw["token"]
    gport = gw["port"]

    log_before = run(c, f"wc -l < {LOG} 2>/dev/null || echo 0", 10).strip()
    health_before = run(c, f"curl -s -H 'Authorization: Bearer {token}' http://127.0.0.1:{gport}/health", 10)
    lines.append(f"health before: {health_before.strip()}")
    lines.append(f"hop log lines before: {log_before}")

    remote_test = f'''
import json, time, urllib.request, uuid
token = {json.dumps(token)}
gport = {gport}
agent_id = {json.dumps(AGENT_ID)}
prompt = {json.dumps(PROMPT)}
base = f"http://127.0.0.1:{{gport}}/api/sendPrompt"
body = {{
    "prompt": prompt,
    "agentId": agent_id,
    "clientNonce": str(uuid.uuid4()),
    "wait": True,
}}
req = urllib.request.Request(base, data=json.dumps(body).encode(), method="POST")
req.add_header("Authorization", "Bearer " + token)
req.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        print("sendPrompt status", r.status)
        print(r.read(2000).decode("utf-8", "replace"))
except Exception as e:
    print("sendPrompt ERR", e)
# wait idle
for i in range(90):
    hreq = urllib.request.Request(f"http://127.0.0.1:{{gport}}/health", headers={{"Authorization": "Bearer "+token}})
    with urllib.request.urlopen(hreq, timeout=8) as r:
        h = json.loads(r.read().decode())
    if not h.get("isBusy"):
        print("idle after", i, "s", json.dumps(h))
        break
    time.sleep(2)
else:
    print("timeout waiting idle")
'''
    sftp = c.open_sftp()
    with sftp.file("/tmp/e2e_send.py", "w") as f:
        f.write(remote_test)
    sftp.close()

    lines.append("=== sendPrompt ===")
    lines.append(run(c, "python3 /tmp/e2e_send.py", 200))

    log_after = run(c, f"tail -n +{int(log_before or 0)+1} {LOG} 2>/dev/null", 10)
    lines.append(f"=== hop log new lines ===\n{log_after}")

    transcript = run(
        c,
        f"tail -5 /home/box/sand-data/agent-transcripts/{AGENT_ID}/{AGENT_ID}.jsonl 2>/dev/null",
        15,
    )
    lines.append(f"=== transcript tail ===\n{transcript}")

    # grep for RoutedModel in recent transcript chunk
    scan = run(
        c,
        f"python3 -c \"import json; fp='/home/box/sand-data/agent-transcripts/{AGENT_ID}/{AGENT_ID}.jsonl'; "
        f"lines=open(fp,encoding='utf-8',errors='replace').read().splitlines()[-30:]; "
        f"[print(l[:500]) for l in lines if 'QWEN_ROUTE' in l or 'RoutedModel' in l or 'qwen' in l.lower()]\"",
        15,
    )
    lines.append(f"=== qwen/routed hits ===\n{scan}")

    # persistence script
    startup = '''#!/bin/bash
pgrep -f token-plan-hop.py >/dev/null && exit 0
nohup env TOKEN_PLAN_HOP_PORT=18792 LOCALAPPDATA=/home/box/.config \\
  python3 /home/box/opengrok/token-plan-hop.py \\
  >> /home/box/opengrok/token-plan-hop.log 2>&1 &
'''
    sftp = c.open_sftp()
    with sftp.file("/home/box/opengrok/start-token-plan-hop.sh", "w") as f:
        f.write(startup)
    sftp.close()
    run(c, "chmod +x /home/box/opengrok/start-token-plan-hop.sh")
    run(c, "(crontab -l 2>/dev/null | grep -v start-token-plan-hop; echo '@reboot /home/box/opengrok/start-token-plan-hop.sh') | crontab -")
    lines.append("=== persistence ===\ncrontab @reboot start-token-plan-hop.sh installed")

    c.close()

    text = "\n".join(lines)
    OUT.write_text(text, encoding="utf-8")

    hop_hit = "chat/completions" in log_after and "200" in log_after
    reply_hit = "QWEN_ROUTE_TEST_OK" in transcript or "QWEN_ROUTE_TEST_OK" in text
    print("HOP_TRAFFIC", hop_hit)
    print("REPLY_OK", reply_hit)
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
