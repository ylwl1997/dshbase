import paramiko
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=300):
    print("====", c[:180], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-15000:] if len(out) > 15000 else out)
    if err.strip():
        print("STDERR:", err[-8000:] if len(err) > 8000 else err)
    return out, err

# Compile DemoAPeriod
run("""cd /opt/soft/Driver/GLink/WGLK220_V3/Demo && \
g++ -g -o DemoAPeriod DemoAPeriod.cpp -fpermissive \
  -I../PublicHead/Commont -I../PublicHead/PublicHead -I../PublicHead/SysDifferent -I../PublicHead/WinDriverHead \
  -D_BUILD_FOR_LINUX_ \
  -L../WinApi/FC_L1_API/.libs -L../WinApi/FC_L0_API/.libs \
  -Wl,-Bstatic -lfcl1 -lfcl0 -Wl,-Bdynamic -lpthread 2>&1""")

run("ls -la /opt/soft/Driver/GLink/WGLK220_V3/Demo/DemoAPeriod /opt/soft/Driver/GLink/WGLK220_V3/Demo/Demo")

# Also try DemoPeriod
run("""cd /opt/soft/Driver/GLink/WGLK220_V3/Demo && \
g++ -g -o DemoPeriod DemoPeriod.cpp -fpermissive \
  -I../PublicHead/Commont -I../PublicHead/PublicHead -I../PublicHead/SysDifferent -I../PublicHead/WinDriverHead \
  -D_BUILD_FOR_LINUX_ \
  -L../WinApi/FC_L1_API/.libs -L../WinApi/FC_L0_API/.libs \
  -Wl,-Bstatic -lfcl1 -lfcl0 -Wl,-Bdynamic -lpthread 2>&1 | tail -40""")

# Write smoke test C++ on remote
smoke = r'''
#include <stdio.h>
#include <stdlib.h>
#include "FC_L1_API.h"

int main() {
    pDevNode_st devnode = NULL;
    printf("Scanning local devices...\n");
    fflush(stdout);
    int r = FC_Dev_ScanLocalDevList(&devnode);
    printf("FC_Dev_ScanLocalDevList ret=%d\n", r);
    int idx = 0;
    for (pDevNode_st p = devnode; p; p = p->pNext, idx++) {
        printf("  board[%d] index=%d\n", idx, p->nIndex);
    }
    if (!devnode) {
        printf("No device found\n");
        return 1;
    }
    FC_DEV_HANDLE m_dev = NULL;
    r = FC_Dev_OpenDevByIndex(0, &m_dev, true);
    printf("OpenDevByIndex(0) ret=%d handle=%p\n", r, (void*)m_dev);
    if (!m_dev) return 2;

    unsigned int nChlNum=0, nGTValue=0, nBankNum=0, nPortNum=0;
    r = FC_Dev_GetChannelNum(m_dev, &nChlNum, &nGTValue, &nBankNum, &nPortNum);
    printf("GetChannelNum ret=%d chl=%u gt=%u bank=%u port=%u\n", r, nChlNum, nGTValue, nBankNum, nPortNum);

    for (unsigned int i = 0; i < nChlNum && i < 8; i++) {
        FC_CHL_HANDLE h = NULL;
        int rr = FC_Dev_OpenChl(m_dev, i, &h);
        printf("  OpenChl(%u) ret=%d h=%p\n", i, rr, (void*)h);
        // try link / port status APIs if available - probe via GetPortLink if exists
    }

    // Try common link status: FC_Dev_GetPortLinkStatus or similar - use Get_Ch if present
    // Print whatever we can without hanging
    printf("Smoke done, closing...\n");
    FC_Dev_CloseDev(m_dev);
    printf("OK\n");
    return 0;
}
'''
# upload via cat
sftp = ssh.open_sftp()
with sftp.file("/tmp/cvg_smoke.cpp", "w") as f:
    f.write(smoke)
sftp.close()

# Find correct header names and link status APIs
run("grep -E 'FC_Dev_ScanLocalDevList|FC_Dev_GetChannelNum|Link|GetPort|PortStatus|Get_Ch_Link' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h | head -60")
run("ls /opt/soft/K72_GLink/Code/demo/ 2>/dev/null; ls /opt/soft/K72_GLink/ 2>/dev/null | head")
