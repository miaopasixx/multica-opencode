#!/usr/bin/env python3
"""OpenCode + Multica 配置管理后台"""
import json, os, sys, signal, subprocess, shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

CONFIG_PATH    = '/root/.config/opencode/opencode.json'
PROVIDERS_PATH = '/data/providers.json'
PID_FILE       = '/tmp/daemon.pid'
PORT           = 8080


# ===================== 工具函数 =====================

def load_providers():
    if os.path.exists(PROVIDERS_PATH):
        with open(PROVIDERS_PATH) as f:
            return json.load(f)
    return {'providers': [], 'default_model': ''}


def save_providers(data):
    os.makedirs('/data', exist_ok=True)
    with open(PROVIDERS_PATH, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_opencode_json(data):
    cfg = {'$schema': 'https://opencode.ai/config.json', 'provider': {}}
    for p in data.get('providers', []):
        cfg['provider'][p['name']] = {
            'npm': '@ai-sdk/openai-compatible',
            'name': p['name'],
            'options': {'baseURL': p['baseURL'], 'apiKey': p['apiKey']},
            'models': {
                m: {
                    'name': m,
                    'limit': {'context': 262144, 'output': 131072},
                    'modalities': {'input': ['text'], 'output': ['text']},
                }
                for m in p.get('models', [])
            },
        }
    if data.get('default_model'):
        cfg['model'] = data['default_model']
    if not cfg['provider']:
        cfg.pop('provider', None)
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def restart_daemon():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, signal.SIGTERM)
        except Exception:
            pass
    proc = subprocess.Popen(['multica', 'daemon', 'start'])
    with open(PID_FILE, 'w') as f:
        f.write(str(proc.pid))
    return True


def daemon_status():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return {'running': True, 'pid': pid}
        except Exception:
            pass
    return {'running': False, 'pid': None}


# ===================== HTTP 服务 =====================

HTML = r'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenCode 配置管理</title>
<style>
  :root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--text:#e1e4ed;--muted:#8b8fa3;--accent:#4f8fff;--danger:#ff5c5c;--green:#3dd68c;--radius:8px}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6}
  .container{max-width:800px;margin:0 auto;padding:24px 16px}
  header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;padding-bottom:12px;border-bottom:1px solid var(--border)}
  h1{font-size:20px;font-weight:600}
  .status{display:flex;align-items:center;gap:12px;font-size:13px;color:var(--muted)}
  .dot{width:8px;height:8px;border-radius:50%}
  .dot.on{background:var(--green);box-shadow:0 0 6px var(--green)}
  .dot.off{background:#555}
  .card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px}
  .card h2{font-size:15px;font-weight:600;margin-bottom:16px;color:var(--text)}
  label{display:block;font-size:13px;color:var(--muted);margin-bottom:4px}
  input,textarea{width:100%;background:#0f1117;border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-size:13px;font-family:inherit;resize:vertical}
  input:focus,textarea:focus{outline:none;border-color:var(--accent)}
  textarea{min-height:80px}
  .row{display:flex;gap:12px;margin-bottom:12px}
  .row>div{flex:1}
  .btn{padding:8px 20px;border-radius:6px;font-size:13px;font-weight:500;cursor:pointer;border:none;transition:opacity .15s}
  .btn:hover{opacity:.85}
  .btn-primary{background:var(--accent);color:#fff}
  .btn-danger{background:transparent;color:var(--danger);border:1px solid var(--danger)}
  .btn-small{background:var(--border);color:var(--text);padding:4px 12px;font-size:12px}
  .provider-list{display:flex;flex-direction:column;gap:8px}
  .provider-item{background:#0f1117;border-radius:6px;padding:14px;display:flex;justify-content:space-between;align-items:center}
  .provider-info{flex:1}
  .provider-name{font-weight:600;font-size:14px}
  .provider-meta{font-size:12px;color:var(--muted);margin-top:2px}
  .model-tag{display:inline-block;background:var(--border);color:var(--text);font-size:11px;padding:1px 8px;border-radius:10px;margin:2px}
  .actions{display:flex;gap:8px}
  .empty{text-align:center;color:var(--muted);padding:24px;font-size:14px}
  .toast{position:fixed;top:16px;right:16px;background:var(--green);color:#000;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:500;opacity:0;transition:opacity .3s;pointer-events:none;z-index:100}
  .toast.show{opacity:1}
  .toast.error{background:var(--danger);color:#fff}
  hr{border:none;border-top:1px solid var(--border);margin:20px 0}
  .note{font-size:12px;color:var(--muted);margin-top:8px}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>OpenCode 配置管理</h1>
    <div class="status">
      <span>Daemon</span>
      <div class="dot" id="daemonDot"></div>
      <span id="daemonText">检测中...</span>
    </div>
  </header>

  <div class="card">
    <h2>添加 Provider</h2>
    <div class="row">
      <div><label>名称</label><input id="pName" placeholder="one-api"></div>
      <div><label>Base URL</label><input id="pURL" placeholder="https://my-api.com/v1"></div>
    </div>
    <div class="row">
      <div><label>API Key</label><input id="pKey" placeholder="sk-xxx"></div>
    </div>
    <label>模型列表（逗号分隔）</label>
    <input id="pModels" placeholder="gpt-4o,claude-sonnet-4-5,qwen-max">
    <div style="margin-top:12px;display:flex;gap:8px;">
      <button class="btn btn-primary" onclick="addProvider()">添加</button>
      <button class="btn btn-small" onclick="saveDefaultModel()">保存默认模型</button>
      <input id="defaultModel" placeholder="默认模型（如 one-api/gpt-4o）" style="width:220px;font-size:12px;">
    </div>
  </div>

  <div class="card">
    <h2>已配置的 Provider</h2>
    <div id="providerList" class="provider-list"></div>
    <div style="margin-top:16px;display:flex;gap:8px;">
      <button class="btn btn-primary" onclick="restartDaemon()">应用并重启 Daemon</button>
      <button class="btn btn-danger" onclick="clearAll()">清空全部</button>
    </div>
  </div>

  <div class="note">
    配置保存在容器挂载卷中，容器重建后自动恢复。<br>
    若不配置任何 Provider，Daemon 将使用 OpenCode 内置免费模型（glm-5-free 等）。
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const $=id=>document.getElementById(id);

function toast(msg,err){const t=$('toast');t.textContent=msg;t.className='toast show'+(err?' error':'');setTimeout(()=>t.className='toast',2500)}

async function load(){
  const r=await fetch('/api/config');
  const d=await r.json();
  renderProviders(d);
  updateStatus();
}

function renderProviders(d){
  const list=$('providerList');
  if(!d.providers||!d.providers.length){
    list.innerHTML='<div class="empty">暂无 Provider，使用 OpenCode 内置免费模型</div>';
  }else{
    list.innerHTML=d.providers.map((p,i)=>`
      <div class="provider-item">
        <div class="provider-info">
          <div class="provider-name">${p.name}</div>
          <div class="provider-meta">${p.baseURL}</div>
          <div style="margin-top:6px">${(p.models||[]).map(m=>`<span class="model-tag">${m}</span>`).join('')}</div>
        </div>
        <div class="actions">
          <button class="btn btn-small" onclick="removeProvider('${p.name}')">删除</button>
        </div>
      </div>
    `).join('');
    $('defaultModel').value=d.default_model||'';
  }
}

async function addProvider(){
  const name=$('pName').value.trim();
  const url=$('pURL').value.trim();
  const key=$('pKey').value.trim();
  const models=$('pModels').value.trim();
  if(!name||!url||!key||!models){toast('请填写全部字段',true);return}
  const r=await fetch('/api/config',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'add',provider:{name,baseURL:url,apiKey:key,models:models.split(',').map(s=>s.trim()).filter(Boolean)}})
  });
  const d=await r.json();
  if(d.ok){toast('已添加');$('pName').value=$('pURL').value=$('pKey').value=$('pModels').value='';load()}
  else toast(d.error||'失败',true)
}

async function removeProvider(name){
  if(!confirm('删除 provider "'+name+'"？'))return;
  const r=await fetch('/api/config',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'remove',name})
  });
  const d=await r.json();
  if(d.ok){toast('已删除');load()}else toast(d.error||'失败',true)
}

async function saveDefaultModel(){
  const v=$('defaultModel').value.trim();
  const r=await fetch('/api/config',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'default_model',model:v})
  });
  const d=await r.json();
  if(d.ok)toast('默认模型已保存');else toast(d.error||'失败',true)
}

async function clearAll(){
  if(!confirm('清空所有 provider 配置？'))return;
  const r=await fetch('/api/config',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'clear'})
  });
  const d=await r.json();
  if(d.ok){toast('已清空');load()}else toast(d.error||'失败',true)
}

async function restartDaemon(){
  const r=await fetch('/api/restart',{method:'POST'});
  const d=await r.json();
  if(d.ok){toast('Daemon 已重启');setTimeout(updateStatus,2000)}else toast(d.error||'重启失败',true)
}

async function updateStatus(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();
    $('daemonDot').className='dot '+(d.running?'on':'off');
    $('daemonText').textContent=d.running?'运行中 (PID '+d.pid+')':'已停止';
  }catch(e){$('daemonText').textContent='无法获取状态'}
}

load();
setInterval(updateStatus,15000);
</script>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._respond(200, 'text/html; charset=utf-8', HTML)
        elif self.path == '/api/config':
            data = load_providers()
            self._respond_json(data)
        elif self.path == '/api/status':
            self._respond_json(daemon_status())
        else:
            self._respond(404, 'text/plain', 'Not Found')

    def do_POST(self):
        body_len = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(body_len)) if body_len else {}

        if self.path == '/api/config':
            data = load_providers()
            action = body.get('action', '')

            if action == 'add':
                p = body.get('provider', {})
                if not p.get('name') or not p.get('baseURL') or not p.get('apiKey') or not p.get('models'):
                    self._respond_json({'ok': False, 'error': '缺少必填字段'})
                    return
                data['providers'] = [x for x in data['providers'] if x['name'] != p['name']]
                data['providers'].append(p)
            elif action == 'remove':
                data['providers'] = [x for x in data['providers'] if x['name'] != body.get('name')]
            elif action == 'clear':
                data['providers'] = []
            elif action == 'default_model':
                data['default_model'] = body.get('model', '')

            save_providers(data)
            build_opencode_json(data)
            self._respond_json({'ok': True})

        elif self.path == '/api/restart':
            data = load_providers()
            build_opencode_json(data)
            try:
                restart_daemon()
                self._respond_json({'ok': True})
            except Exception as e:
                self._respond_json({'ok': False, 'error': str(e)})
        else:
            self._respond(404, 'text/plain', 'Not Found')

    def _respond(self, code, ct, body):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body.encode('utf-8') if isinstance(body, str) else body)

    def _respond_json(self, data):
        self._respond(200, 'application/json', json.dumps(data, ensure_ascii=False))

    def log_message(self, format, *args):
        pass


def main():
    if '--restore' in sys.argv:
        data = load_providers()
        build_opencode_json(data)
        print(f'[admin] 已恢复 {len(data.get("providers",[]))} 个 provider')
        return

    if '--serve' in sys.argv:
        server = HTTPServer(('0.0.0.0', PORT), Handler)
        print(f'[admin] 管理界面运行在 http://0.0.0.0:{PORT}')
        server.serve_forever()


if __name__ == '__main__':
    main()
