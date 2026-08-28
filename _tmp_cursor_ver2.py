import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)

def run(cmd, timeout=45):
    print(">>>>", cmd[:200], flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + "\n" + err).encode("ascii", "replace").decode("ascii")
    print(text[-3500:], flush=True)
    print("exit:", code, flush=True)

# Electron version often prints to stdout after flags
run("timeout -s KILL 12 env DISPLAY=:1 HOME=/home/box /home/box/Applications/cursor.AppDir/usr/share/cursor/cursor --no-sandbox --disable-gpu-sandbox --version; echo RC=$?")
run("test -x /home/box/.local/bin/cursor && test -x /home/box/Applications/cursor.AppDir/AppRun && echo BINARIES_OK")
run("grep -n PATH /home/box/.bashrc /home/box/.profile | head -10")
client.close()
