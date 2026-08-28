import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)

def run(cmd, timeout=300):
    print(">>>>", cmd[:240])
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-4000:] if len(out) > 4000 else out)
    if err.strip():
        print("STDERR:", (err[-2500:] if len(err) > 2500 else err))
    print("exit:", code)
    return code, out, err

# Check FUSE tools
run("command -v fusermount fusermount3; dpkg -l | grep -i fuse | head -20; ls -l /dev/fuse")

# Quick AppImage self-test (may fail without FUSE user tools)
run("chmod +x /home/box/Applications/Cursor-3.17.21-x86_64.AppImage; cd /home/box/Applications && ./Cursor-3.17.21-x86_64.AppImage --appimage-help 2>&1 | head -40", timeout=60)

client.close()
