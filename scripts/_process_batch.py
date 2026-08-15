import json, os, re, subprocess, urllib.request

TOK = re.search(r'ghp_[A-Za-z0-9]+', open('C:/Users/Administrator/.claude/projects/C--Users-Administrator/memory/api-credentials.md', encoding='utf-8').read()).group(0)
DSK = re.search(r'DEEPSEEK_API_KEY:\s*(\S+)', open('C:/Users/Administrator/.dsh/.credentials.yaml', encoding='utf-8').read()).group(1)
env = {**os.environ, 'GITHUB_TOKEN': TOK, 'DEEPSEEK_API_KEY': DSK, 'PYTHONIOENCODING': 'utf-8'}

H = {'Authorization': 'Bearer ' + TOK, 'User-Agent': 'dshbase', 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'}
BASE = 'https://api.github.com/repos/ylwl1997/dshbase'

def gh(path, data=None, method=None):
    req = urllib.request.Request(BASE + path, data=data, headers=H, method=method)
    return urllib.request.urlopen(req)

def comment(n, body):
    gh(f'/issues/{n}/comments', json.dumps({'body': body}).encode())

def close(n):
    gh(f'/issues/{n}', json.dumps({'state': 'closed'}).encode(), 'PATCH')

def ingest(repo, npm, cat):
    cmd = ['python', 'scripts/ingest-plugin.py', repo, '--json']
    if npm: cmd += ['--npm', npm]
    if cat: cmd += ['--category', cat]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {'status': 'error', 'message': r.stderr[-300:]}

# --- #23 dsh-doc-share（完整提交，正常收录）---
r23 = ingest('https://github.com/dawsondx/dsh-doc-share', 'dsh-doc-share', 'Sessions & Messages')
comment(23, r23.get('message', '已处理'))
if r23['status'] in ('accepted', 'existing'):
    close(23)
print('#23 ->', r23['status'])

# --- #17 dsh-ai-battle（之前拒绝，新策略：先收录+标注）---
r17 = ingest('https://github.com/Gxk96/dsh-ai-battle', '', 'UI Enhancements')
comment(17, r17.get('message', '已处理'))
if r17['status'] in ('accepted', 'existing'):
    close(17)
print('#17 ->', r17['status'])

# --- #24 dsh-tokensave（重复提交，已在目录）---
comment(24, '✅ dsh-tokensave 已在目录中（之前已收录），感谢重新提交！安装：`dsh plugin add github:Miku196/dsh-tokensave`')
close(24)
print('#24 -> 已收录(重复)')

# --- #22 dsh-tokensave（已回复过，现在关闭）---
close(22)
print('#22 -> 已关闭')
