#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

patterns = [
    "model-bindings", "model_bindings", "modelBindings", "ModelBindings",
    "hopBaseUrl", "hopBase", "hop_base", "18792", "token-plan",
    "bindings.json", "resolveModel", "modelRoute", "customModel",
    "openai-compatible", "compatible-mode",
]
for p in patterns:
    _, o, _ = c.exec_command(
        f"grep -c '{p}' /home/box/sand-host/host-main.cjs 2>/dev/null || echo 0",
        timeout=30,
    )
    cnt = o.read().decode().strip()
    if cnt and cnt != "0":
        print(f"{p}: {cnt} hits")
        _, o2, _ = c.exec_command(
            f"grep -aoE '.{{0,50}}{p}.{{0,50}}' /home/box/sand-host/host-main.cjs | head -3",
            timeout=30,
        )
        for line in o2.read().decode("utf-8", "replace").splitlines():
            print("  ", line[:120])

# box-store sync - does Windows push bindings?
_, o, _ = c.exec_command(
    "grep -r 'model-bindings' /usr/local/bin /exec-daemon 2>/dev/null | head -15",
    timeout=30,
)
print("\n/usr/local/bin grep:", o.read().decode("utf-8", "replace")[:1500] or "(none)")

# check if sand syncs from Windows - box-store
_, o, _ = c.exec_command(
    "strings /usr/local/bin/sand-session-sync.mjs 2>/dev/null | grep -i bind | head -10",
    timeout=15,
)
print("\nsand-session-sync bind:", o.read().decode("utf-8", "replace")[:800] or "(none)")

c.close()
