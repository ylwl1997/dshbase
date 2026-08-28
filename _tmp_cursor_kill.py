import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)
stdin, stdout, stderr = c.exec_command("pkill -f '/home/box/Applications/cursor.AppDir/usr/share/cursor/cursor' || true; pgrep -af 'Applications/cursor' || echo no_cursor_procs; echo OK", timeout=20)
print(stdout.read().decode("ascii","replace"))
c.close()
