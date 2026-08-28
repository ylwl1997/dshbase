import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("100.66.1.16", username="root", password="60851.org", timeout=20)

# Pull Smart init / short msg procedure from manuals + any demos on server
cmds = [
  r"""python3 - <<'PY'
import re,os
for p in ['/tmp/jlk_sw_full.txt','/tmp/jlk_hw_full.txt']:
  if not os.path.exists(p):
    print('missing',p); continue
  src=open(p,encoding='utf-8',errors='replace').read().splitlines()
  print('====',p,'====')
  # find short msg software steps / init
  for key in ['短报文模式下数据传输','初始化 SmartNC','SmartNC 工作在短报文','FIFO_WR_SEL','应用层软件']:
    for i,l in enumerate(src):
      if key in l:
        for j in range(i, min(i+35,len(src))):
          print(f'{j+1}: {src[j]}')
        print('----')
        break
PY""",
  r"""find /opt/soft /root -iname '*smart*' -o -iname '*SmartNC*' 2>/dev/null | head -40""",
  r"""ls /opt/soft/K72_GLink/Doc/DEMO/; ls /tmp/k72_extract 2>/dev/null | head""",
]
for c in cmds:
  print('====CMD====')
  stdin,stdout,stderr=client.exec_command(c, timeout=60)
  print(stdout.read().decode('utf-8','replace')[:10000])
client.close()
