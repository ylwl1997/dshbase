import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=600):
    print("====", c[:120], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-8000:] if len(out) > 8000 else out)
    if err.strip():
        print("STDERR:", err[-4000:] if len(err) > 4000 else err)
    return out, err

run("ls -la /opt/soft/Driver/GLink/WGLK220_V3/")
run("find /opt/soft/Driver/GLink/WGLK220_V3 -maxdepth 3 -type d")
run("ls /opt/soft/Driver/GLink/WGLK220_V3/install/lib 2>/dev/null; ls /opt/soft/Driver/GLink/WGLK220_V3/WinApi 2>/dev/null; find /opt/soft/Driver/GLink/WGLK220_V3 -name 'libfc*.so*' -o -name 'libfc*.a' 2>/dev/null | head")
run("file /opt/soft/Driver/GLink/WGLK220_V3/Demo/Demo; ldd /opt/soft/Driver/GLink/WGLK220_V3/Demo/Demo 2>&1 | head -20")
run("which autoreconf g++ gcc make; g++ --version | head -1")
# try build
run("cd /opt/soft/Driver/GLink/WGLK220_V3 && (test -f Makefile && make -j$(nproc) 2>&1 | tail -50)")
ssh.close()
