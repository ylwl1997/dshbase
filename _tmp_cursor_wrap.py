import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)

def run(cmd, timeout=300):
    print(">>>>", cmd[:320])
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-6000:] if len(out) > 6000 else out)
    if err.strip():
        print("STDERR:", (err[-3000:] if len(err) > 3000 else err))
    print("exit:", code)
    return code, out, err

# Create launch wrappers via a here-doc on remote
script = r'''
set -e
# --- GUI launcher ---
cat > /home/box/.local/bin/cursor-gui << 'EOF'
#!/usr/bin/env bash
# Launch Cursor IDE on Bot desktop (sandbox-friendly)
set -euo pipefail
APPDIR="${CURSOR_APPDIR:-/home/box/Applications/cursor.AppDir}"
APPIMAGE="/home/box/Applications/Cursor-3.17.21-x86_64.AppImage"
export DISPLAY="${DISPLAY:-:1}"
# Prefer extracted AppRun (no FUSE required)
BIN=""
if [ -x "$APPDIR/AppRun" ]; then
  BIN="$APPDIR/AppRun"
elif [ -x "$APPIMAGE" ]; then
  BIN="$APPIMAGE"
else
  echo "Cursor not found under $APPDIR or $APPIMAGE" >&2
  exit 1
fi
exec "$BIN" --no-sandbox --disable-gpu-sandbox "$@"
EOF
chmod +x /home/box/.local/bin/cursor-gui

# --- CLI-friendly symlink name ---
cat > /home/box/.local/bin/cursor << 'EOF'
#!/usr/bin/env bash
# Cursor IDE launcher (also used as `cursor` CLI entry)
exec /home/box/.local/bin/cursor-gui "$@"
EOF
chmod +x /home/box/.local/bin/cursor

# --- Desktop entry ---
ICON=""
if [ -f /home/box/Applications/cursor.AppDir/co.anysphere.cursor.png ]; then
  ICON=/home/box/Applications/cursor.AppDir/co.anysphere.cursor.png
elif [ -f /home/box/Applications/cursor.AppDir/cursor.png ]; then
  ICON=/home/box/Applications/cursor.AppDir/cursor.png
else
  ICON=$(find /home/box/Applications/cursor.AppDir -name '*.png' 2>/dev/null | head -1)
fi

cat > /home/box/.local/share/applications/cursor.desktop << EOF
[Desktop Entry]
Name=Cursor
Comment=Cursor AI IDE
Exec=/home/box/.local/bin/cursor-gui %F
Icon=${ICON}
Terminal=false
Type=Application
Categories=Development;IDE;TextEditor;
StartupWMClass=Cursor
MimeType=text/plain;inode/directory;
EOF
chmod +x /home/box/.local/share/applications/cursor.desktop
cp -f /home/box/.local/share/applications/cursor.desktop /home/box/Desktop/cursor.desktop
chmod +x /home/box/Desktop/cursor.desktop

# Ensure PATH for interactive shells
if ! grep -q '.local/bin' /home/box/.bashrc 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/box/.bashrc
fi
if ! grep -q '.local/bin' /home/box/.profile 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/box/.profile
fi

# README for user
cat > /home/box/CURSOR_README.txt << 'EOF'
Cursor IDE (Linux x64 AppImage 3.17.21)
=======================================
Installed:
  AppImage: /home/box/Applications/Cursor-3.17.21-x86_64.AppImage
  Extracted: /home/box/Applications/cursor.AppDir/  (preferred; no FUSE)
  Launchers: ~/.local/bin/cursor  and  ~/.local/bin/cursor-gui
  Desktop:   ~/Desktop/cursor.desktop

GUI (VNC / xfce desktop):
  Double-click Desktop "Cursor" or run in terminal:
    cursor
    # or force display:
    DISPLAY=:1 cursor

SSH with GUI:
  DISPLAY=:1 cursor &

Sandbox flags:
  Launchers pass --no-sandbox --disable-gpu-sandbox (required in this sand).

CLI agent (if installed):
  cursor-agent --help
EOF

echo "Wrappers OK"
ls -la /home/box/.local/bin/cursor /home/box/.local/bin/cursor-gui /home/box/Desktop/cursor.desktop
echo "ICON=$ICON"
'''
run(script)

# Install cursor-agent via official installer (non-interactive)
run("NO_COLOR=1 bash /tmp/cursor-install.sh 2>&1 | tee /tmp/cursor-agent-install.log | tail -80", timeout=300)

client.close()
