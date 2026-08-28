import paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)

def run(cmd, timeout=120):
    print(">>>>", cmd[:280])
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\nSTDERR:\n" + err if err.strip() else "")).encode("ascii", "replace").decode("ascii")
    print(text[-5000:] if len(text) > 5000 else text)
    print("exit:", code)
    return code, out, err

# Kill any hung cursor from --version test
run("pkill -f 'cursor.AppDir' 2>/dev/null || true; pkill -f 'Cursor-3.17.21' 2>/dev/null || true; sleep 1; pgrep -af cursor | head -20 || true")

# Agent version/help
run("export PATH=$HOME/.local/bin:$PATH; cursor-agent --version 2>&1; echo ---; agent --version 2>&1; echo ---; cursor-agent --help 2>&1 | head -40")

# Better IDE version: use electron binary with ELECTRON_RUN_AS_NODE or just product.json + --help short timeout
run("timeout 25 env DISPLAY=:1 /home/box/Applications/cursor.AppDir/usr/share/cursor/cursor --no-sandbox --version 2>&1 | head -40 || true")

# Disk cleanup: keep AppImage + AppDir; remove install junk
run("""
rm -f /tmp/cursor-install.sh /tmp/cursor-agent-install.log
# remove any leftover extract dirs
rm -rf /home/box/Applications/squashfs-root
# keep both AppImage and extracted AppDir
du -sh /home/box/Applications/* /home/box/.local/share/cursor-agent 2>/dev/null
df -h / | tail -1
""")

# Sanity: reverse-ssh / sand services still up
run("systemctl --user list-units --type=service 2>/dev/null | head -5; ps aux | grep -E 'sshd|reverse|sand-|x11vnc|nodebaby' | grep -v grep | head -25; ss -tlnp 2>/dev/null | head -20 || netstat -tlnp 2>/dev/null | head -20")

# Update README with agent info
run(r'''
cat > /home/box/CURSOR_README.txt << 'EOF'
Cursor on Bot PC (hostname: cursor)
===================================
Installed (official Linux x64):
  IDE AppImage : /home/box/Applications/Cursor-3.17.21-x86_64.AppImage  (~277MB)
  Extracted    : /home/box/Applications/cursor.AppDir/   (preferred launch path; no FUSE)
  Version      : 3.17.21 (commit 8f2a112cb284)
  Launchers    : ~/.local/bin/cursor   ~/.local/bin/cursor-gui
  Desktop icon : ~/Desktop/cursor.desktop  (+ ~/.local/share/applications/cursor.desktop)
  Agent CLI    : ~/.local/bin/cursor-agent  (also: agent)
                 version package: 2026.08.25-3e8eec8 under ~/.local/share/cursor-agent/

Start GUI (VNC / xfce desktop):
  - Double-click Desktop "Cursor"
  - Or terminal:  cursor
  - SSH then GUI: DISPLAY=:1 cursor &
  Default DISPLAY in launcher is :1 (matches x11vnc). Use :2/:3 if needed.

Start Agent CLI (no full IDE):
  cursor-agent --help
  agent --help

Sandbox notes:
  - Launchers add --no-sandbox --disable-gpu-sandbox (Electron in sand).
  - dbus/system_bus_socket warnings are expected and usually OK.
  - No fusermount package; extracted AppDir avoids FUSE mounts.
  - Overlay root (~115G free). Persistence: /home/box content survives typical sand
    session; full sand image reset would wipe Applications — re-run install if so.
  - Did not touch reverse-ssh / NodeBaby / sand-* services.

EOF
cat /home/box/CURSOR_README.txt
''')

client.close()
print("ALL_DONE")
