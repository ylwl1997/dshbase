import paramiko, textwrap
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=30)

def run(cmd, timeout=600):
    print(">>>>", cmd[:300])
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-5000:] if len(out) > 5000 else out)
    if err.strip():
        print("STDERR:", (err[-2500:] if len(err) > 2500 else err))
    print("exit:", code)
    return code, out, err

# Extract AppImage for sandbox reliability (no fusermount package)
run("""
set -e
cd /home/box/Applications
if [ ! -x cursor.AppDir/AppRun ]; then
  rm -rf squashfs-root cursor.AppDir
  ./Cursor-3.17.21-x86_64.AppImage --appimage-extract
  mv squashfs-root cursor.AppDir
fi
ls -la cursor.AppDir/AppRun cursor.AppDir/cursor 2>/dev/null | head -20
# version probe from product.json if present
find cursor.AppDir -name product.json 2>/dev/null | head -5
""", timeout=180)

client.close()
