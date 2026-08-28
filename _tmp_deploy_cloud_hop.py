#!/usr/bin/env python3
"""Deploy token-plan-hop to Grok Bot cloud sand box."""
import json
import os
import paramiko
from pathlib import Path

HOST = "64.83.13.119"
PORT = 22022
USER = "box"
PASSWORD = "PBkNIKuNgv3OrOTMTiPK"

HOP_SRC = Path(r"C:\Users\Administrator\opengrok\tools\token-plan-hop.py")
ENV_SRC = Path(os.path.expandvars(r"%LOCALAPPDATA%\grokbot\token-plan.env"))

AGENTS = {
    "a67d15ec-b377-46ba-b6f3-182a0982f683": ("yest", "qwen3.6-flash"),
    "f9cf215c-f7c0-4d58-97b9-79d1ac04db5e": ("New Bot", "qwen3.7-plus"),
    "acdb77da-34a3-4188-9135-9780e8ed1721": ("游小二", "qwen3.7-max"),
}

BINDINGS = {
    "_comment": "Token Plan on cloud sand hop — keys in ~/.config/grokbot/token-plan.env",
    "agents": {},
}

for aid, (name, model) in AGENTS.items():
    BINDINGS["agents"][aid] = {
        "name": f"TokenPlan {name} ({model})",
        "modelId": model,
        "provider": "qwen-token-plan",
        "hopBaseUrl": "http://127.0.0.1:18792/v1",
        "maxMode": False,
        "parameters": [],
    }


def run(client, cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                   timeout=20, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()

    print("=== 1) discover bindings path ===")
    out, _ = run(client, r'grep -r "model-bindings" /home/box/sand-host 2>/dev/null | head -20')
    print(out or "(no grep hits in sand-host)")

    out2, _ = run(client, r'grep -r "hopBaseUrl" /home/box/sand-host 2>/dev/null | head -10')
    print(out2 or "(no hopBaseUrl hits)")

    out3, _ = run(client, "ls -la /home/box/sand-data/agents/ 2>/dev/null")
    print(out3)

    print("=== 2) upload hop + env ===")
    remote_dir = "/home/box/opengrok"
    run(client, f"mkdir -p {remote_dir} /home/box/.config/grokbot")
    sftp.put(str(HOP_SRC), f"{remote_dir}/token-plan-hop.py")
    sftp.put(str(ENV_SRC), "/home/box/.config/grokbot/token-plan.env")
    run(client, f"chmod 600 /home/box/.config/grokbot/token-plan.env && chmod +x {remote_dir}/token-plan-hop.py")

    # Also try common binding locations
    bindings_json = json.dumps(BINDINGS, ensure_ascii=False, indent=2) + "\n"
    binding_paths = [
        "/home/box/sand-data/model-bindings.json",
        "/home/box/model-bindings.json",
        "/home/box/agent-data/model-bindings.json",
    ]
    for p in binding_paths:
        with sftp.file(p, "w") as f:
            f.write(bindings_json)
        run(client, f"chmod 644 {p}")
        print(f"wrote {p}")

    # Windows bindings too
    win_bindings = Path(os.path.expandvars(r"%APPDATA%\Grok Bot\model-bindings.json"))
    win_bindings.write_text(bindings_json, encoding="utf-8")
    print(f"wrote Windows {win_bindings}")

    print("=== 3) start hop on cloud ===")
    run(client, "pkill -f token-plan-hop.py 2>/dev/null || true")
    start_cmd = (
        "nohup env TOKEN_PLAN_HOP_PORT=18792 "
        "LOCALAPPDATA=/home/box/.config "
        f"python3 {remote_dir}/token-plan-hop.py "
        ">> /home/box/opengrok/token-plan-hop.log 2>&1 & echo $!"
    )
    out, err = run(client, start_cmd)
    print("started pid:", out.strip(), err[:200] if err else "")

    import time
    time.sleep(2)

    print("=== 4) verify hop ===")
    out, _ = run(client, "curl -s http://127.0.0.1:18792/healthz")
    print("healthz:", out)

    test_body = json.dumps({
        "model": "qwen3.6-flash",
        "messages": [{"role": "user", "content": "Reply exactly: CLOUD_QWEN_OK"}],
        "max_tokens": 32,
        "stream": False,
    })
    # escape for shell
    escaped = test_body.replace("'", "'\\''")
    out, _ = run(client, f"curl -s -X POST http://127.0.0.1:18792/v1/chat/completions -H 'Content-Type: application/json' -d '{escaped}'")
    print("chat test:", out[:800])

    print("=== 5) check process ===")
    out, _ = run(client, "ss -tlnp | grep 18792; pgrep -af token-plan-hop")
    print(out)

    sftp.close()
    client.close()
    print("DONE")


if __name__ == "__main__":
    main()
