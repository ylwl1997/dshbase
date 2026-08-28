import paramiko
import sys
import time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=180):
    print("====", c[:160], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-10000:] if len(out) > 10000 else out)
    if err.strip():
        print("STDERR:", err[-3000:] if len(err) > 3000 else err)
    return out, err

# Enhanced: set GLink protocol + 2.5G then recheck link
code = r'''
#include <stdio.h>
#include <unistd.h>
#include "FC_L1_API.h"

int main(void) {
    pDevNode_st list=NULL;
    FC_Dev_ScanLocalDevList(&list);
    FC_DEV_HANDLE h=NULL;
    if (FC_Dev_OpenDevByIndex(0,&h,FC_TRUE)!=0 || !h){printf("open fail\n");return 1;}
    FC_DWORD dma=0,gt=0,bank=0,port=0;
    FC_Dev_GetChannelNum(h,&dma,&gt,&bank,&port);
    printf("chl=%u gt=%u bank=%u port=%u\n",dma,gt,bank,port);

    /* open chl 0, set protocol GLink */
    FC_CHL_HANDLE ch=NULL;
    int r=FC_Dev_OpenChl(h,0,&ch);
    printf("OpenChl ret=%d\n",r);

    /* Demo uses FC_Dev_Set_Ch_Protocol_GTPort(m_dev,i,0x1,tempvalue) */
    /* try SetAllPortSpeed for 2.5G to match K72 */
    r=FC_Dev_SetAllPortSpeed_Bank(h,0,PORT_SPEED_2p5G);
    printf("SetAllPortSpeed_Bank(0,2.5G) ret=%d\n",r);
    usleep(500000);

    for(int i=0;i<(int)(dma?dma:1);i++){
      for(int j=0;j<(int)(port?port:2);j++){
        FC_DWORD st=0;
        FC_Dev_Get_PortLinkState(h,i,(FC_WORD)j,&st);
        printf("after 2.5G: st=%u port=%d state=%u\n",i,j,st);
      }
    }

    r=FC_Dev_SetAllPortSpeed_Bank(h,0,PORT_SPEED_5G);
    printf("SetAllPortSpeed_Bank(0,5G) ret=%d\n",r);
    usleep(500000);
    for(int j=0;j<2;j++){
      FC_DWORD st=0;
      FC_Dev_Get_PortLinkState(h,0,(FC_WORD)j,&st);
      printf("after 5G: port=%d state=%u\n",j,st);
    }

    if(ch) FC_Dev_CloseChl(ch);
    FC_Dev_Close(h);
    return 0;
}
'''
sftp=ssh.open_sftp()
with sftp.file("/tmp/cvg_speed.cpp","w") as f: f.write(code)
sftp.close()

run("""cd /tmp && g++ -g -o cvg_speed cvg_speed.cpp -fpermissive \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/Commont \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/SysDifferent \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/WinDriverHead \
  -L/opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L1_API/.libs \
  -L/opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L0_API/.libs \
  -Wl,-Bstatic -lfcl1 -lfcl0 -Wl,-Bdynamic -lpthread 2>&1 && /tmp/cvg_speed""")

# Confirm both drivers still ok
run("lsmod | grep -E 'cvg|xdma'; ls -la /dev/cvgdev* /dev/xdma0_* 2>/dev/null; lspci -nn -s 01:00.0 -s 8c:00.0")

# Quick note on K72 address model from docs/code
run("grep -n 'SA\\|NC_ID\\|0x10\\|station\\|站址\\|SID\\|DID' /opt/soft/K72_GLink/Doc/*.md 2>/dev/null | head -40; grep -n 'CtrlNcInit\\|nSID\\|SA' /opt/soft/K72_GLink/Code/demo/test_glink_api.c | head -30")
run("ls /opt/soft/Driver/GLink/Doc/ 2>/dev/null; head -5 /opt/soft/K72_GLink/README.md 2>/dev/null")
ssh.close()
