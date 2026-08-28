import paramiko, time
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)

def run(cmd, timeout=600):
    print(">>>>", cmd[:200])
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:] if len(out) > 3000 else out)
    if err.strip():
        print("STDERR:", err[-2000:] if len(err) > 2000 else err)
    print("exit:", code)
    return code, out, err

# Prepare dirs
run("mkdir -p /home/box/Applications /home/box/.local/bin /home/box/.local/share/applications /home/box/Desktop")

# Download AppImage (stable 3.17.21)
url = "https://downloads.cursor.com/production/8f2a112cb2845a97b75fd932ea5c470579ca4063/linux/x64/Cursor-3.17.21-x86_64.AppImage"
run(f'cd /home/box/Applications && curl -fL --retry 3 --retry-delay 2 -o Cursor-3.17.21-x86_64.AppImage "{url}" && ls -lh Cursor-3.17.21-x86_64.AppImage && chmod +x Cursor-3.17.21-x86_64.AppImage', timeout=600)

# Also fetch CLI install script info / agent if available
run("curl -fsSL https://cursor.com/install -o /tmp/cursor-install.sh 2>&1 | tail -5; head -c 500 /tmp/cursor-install.sh 2>/dev/null; echo; wc -c /tmp/cursor-install.sh 2>/dev/null")

client.close()
