import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=180):
    print("====", c, "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    return out, err

# Load cvgDrv
run("dmesg -C 2>/dev/null; insmod /opt/soft/Driver/GLink/Driver/cvgDrv.ko; echo exit:$?")
run("lsmod | grep -E 'cvg|xdma' || true")
run("ls -la /dev/cvgdev* 2>/dev/null || true")
run("dmesg | tail -40")
run("lspci -vvv -s 8c:00.0 2>/dev/null | head -60")
run("cat /opt/soft/Driver/GLink/WGLK220_V3/b.sh")
run("ls -la /opt/soft/Driver/GLink/WGLK220_V3/Demo/")
run("cat /opt/soft/Driver/GLink/WGLK220_V3/Demo/README 2>/dev/null; ls /opt/soft/Driver/GLink/WGLK220_V3/Demo/")
# Doc - use find for Chinese filename
run("find /opt/soft/Driver/GLink -maxdepth 1 -name '*.md' -exec cat {} \\;")
ssh.close()
