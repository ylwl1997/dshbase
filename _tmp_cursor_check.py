import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)
cmds = [
    "uname -m; hostname; head -5 /etc/os-release",
    "which cursor cursor-agent 2>/dev/null; ls -la ~/Applications /opt/cursor /usr/local/bin/cursor 2>/dev/null; ls ~/.local/bin/cursor* 2>/dev/null",
    "dpkg -l 2>/dev/null | grep -i cursor || true",
    "find /home/box /opt /usr -maxdepth 3 -iname '*cursor*' 2>/dev/null | head -40",
    "echo DISPLAY=$DISPLAY; echo XDG=$XDG_SESSION_TYPE; ps aux | grep -E 'x11vnc|xfce|Xorg' | grep -v grep | head -10",
    "df -h / /home /tmp 2>/dev/null; free -h | head -2",
    "fusermount -V 2>/dev/null; ls /dev/fuse 2>/dev/null; dpkg -l libfuse* 2>/dev/null | tail -5",
]
for c in cmds:
    print("==== CMD ====")
    print(c)
    print("==== OUT ====")
    stdin, stdout, stderr = client.exec_command(c, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[:800])
client.close()
print("DONE")
