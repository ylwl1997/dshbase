import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stdout.reconfigure(line_buffering=True)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("connecting...")
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)
print("connected")

def run(cmd, timeout=60):
    print(">>>>", cmd[:200], flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + (("\nERR:" + err) if err.strip() else "")).encode("ascii", "replace").decode("ascii")
    print(text[-4000:] if len(text) > 4000 else text, flush=True)
    print("exit:", code, flush=True)
    return code

run("pkill -f '/home/box/Applications/cursor.AppDir' || true; pkill -f 'Cursor-3.17.21' || true; echo killed")
run("export PATH=$HOME/.local/bin:$PATH; ls -la ~/.local/bin/cursor ~/.local/bin/cursor-gui ~/.local/bin/cursor-agent; cursor-agent --version; agent --version")
run("python3 -c \"import json;p=json.load(open('/home/box/Applications/cursor.AppDir/usr/share/cursor/resources/app/product.json'));print(p.get('version'), p.get('commit','')[:12])\"")
run("du -sh /home/box/Applications/Cursor-3.17.21-x86_64.AppImage /home/box/Applications/cursor.AppDir /home/box/.local/share/cursor-agent; ls /home/box/Desktop/cursor.desktop /home/box/CURSOR_README.txt 2>&1")
run("rm -f /tmp/cursor-install.sh /tmp/cursor-agent-install.log; rm -rf /home/box/Applications/squashfs-root; echo cleaned")
run("pgrep -af 'x11vnc|sshd' | head -15; ss -tln | head -15")
# Write README without special dashes
run("""cat > /home/box/CURSOR_README.txt << 'EOF'
Cursor on Bot PC (hostname: cursor)
===================================
Installed (official Linux x64):
  IDE AppImage : /home/box/Applications/Cursor-3.17.21-x86_64.AppImage
  Extracted    : /home/box/Applications/cursor.AppDir/  (preferred; no FUSE)
  Version      : 3.17.21 (commit 8f2a112cb284)
  Launchers    : ~/.local/bin/cursor  ~/.local/bin/cursor-gui
  Desktop icon : ~/Desktop/cursor.desktop
  Agent CLI    : ~/.local/bin/cursor-agent  (alias: agent)
                 package 2026.08.25-3e8eec8 in ~/.local/share/cursor-agent/

GUI start (VNC/xfce):
  Double-click Desktop Cursor, or:  cursor
  From SSH:  DISPLAY=:1 cursor &
  Launcher default DISPLAY=:1 (use :2/:3 if needed)

Agent CLI:
  cursor-agent --help
  agent --help

Caveats:
  - Launchers pass --no-sandbox --disable-gpu-sandbox
  - dbus warnings expected in sand
  - No fusermount; use extracted AppDir
  - Full sand image reset may wipe /home/box Applications
  - reverse-ssh / NodeBaby / sand services not modified
EOF
wc -l /home/box/CURSOR_README.txt
""")
client.close()
print("ALL_DONE", flush=True)
