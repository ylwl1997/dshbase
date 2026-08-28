import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)

def run(cmd, timeout=180):
    print(">>>>", cmd[:280])
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\nSTDERR:\n" + err if err.strip() else "")).encode("ascii", "replace").decode("ascii")
    print(text[-7000:] if len(text) > 7000 else text)
    print("exit:", code)
    return code, out, err

# Check agent install log
run("wc -l /tmp/cursor-agent-install.log 2>/dev/null; tail -c 4000 /tmp/cursor-agent-install.log 2>/dev/null | cat -v")

# Which binaries now
run("export PATH=$HOME/.local/bin:$PATH; which cursor cursor-gui cursor-agent 2>/dev/null; ls -la ~/.local/bin/ | head -40; ls -la ~/.cursor-agent 2>/dev/null | head; find /home/box -maxdepth 3 -name 'cursor-agent' 2>/dev/null | head")

# Version from product.json
run("python3 -c \"import json; p=json.load(open('/home/box/Applications/cursor.AppDir/usr/share/cursor/resources/app/product.json')); print('version', p.get('version')); print('name', p.get('nameShort') or p.get('applicationName')); print('commit', (p.get('commit') or '')[:12])\"")

# Try --version non-interactive
run("export PATH=$HOME/.local/bin:$PATH; DISPLAY=:1 /home/box/.local/bin/cursor --version 2>&1 | head -30", timeout=90)

client.close()
