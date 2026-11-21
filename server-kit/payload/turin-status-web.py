#!/usr/bin/env python3
"""Read-only setup dashboard on 127.0.0.1:8099, reached from the Mac over the SSH tunnel. Never accepts credentials.
Shows ids, waves, sizes and states only (no model names)."""
import argparse,json,pathlib,subprocess,threading,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
STATE=pathlib.Path('/var/lib/turin/phase.json')
HTML='''<!doctype html><meta charset="utf-8"><title>EPYC Studio Setup</title>
<style>body{font:16px system-ui;max-width:1100px;margin:2em auto;background:#10151e;color:#e7edf7}a{color:#75ccff}pre{white-space:pre-wrap}section{padding:1em;background:#1b2535;margin:1em 0}progress{width:100%}</style>
<h1>EPYC Studio — Live Setup</h1><p>Processing runs on the Linux GPU server, not your Mac. No completion-time promises.</p>
<section><h2 id="phase">Connecting…</h2><p id="message"></p><p id="ready"></p></section>
<section><h2>Actual hardware telemetry</h2><pre id="hardware"></pre></section>
<section><h2>Verified downloads</h2><progress id="progress" value="0" max="100"></progress><div id="waves"></div><details><summary>Every file</summary><pre id="models"></pre></details></section>
<section><h2>Recent provisioning log</h2><pre id="log"></pre></section>
<p>Open the apps with <b>Connect-EPYC-Studio.command</b> on the Mac (SSH tunnel). The remote-desktop password is set over SSH with <code>turin-first-login</code>, never on this page. This server holds no download tokens.</p>
<script>async function poll(){try{let s=await(await fetch('/api/status',{cache:'no-store'})).json();for(let k of ['phase','message'])document.getElementById(k).textContent=s[k]||'Unknown';document.getElementById('hardware').textContent=JSON.stringify(s.telemetry,null,2);document.getElementById('models').textContent=JSON.stringify(s.downloads,null,2);let wv=document.getElementById('waves');wv.textContent='';for(let [k,w] of Object.entries(s.waves||{})){let p=document.createElement('p');p.textContent=w.name+': '+w.verified+'/'+w.files+' files verified, '+w.percent+'%'+(w.blocked?' | blocked '+w.blocked:'')+(w.skipped?' | skipped '+w.skipped:'');let b=document.createElement('progress');b.max=100;b.value=w.percent;wv.append(p,b);}document.getElementById('progress').value=s.download_progress_percent;document.getElementById('ready').textContent=Object.entries(s.services).map(([k,v])=>k+': '+v).join(' | ');document.getElementById('log').textContent=s.log;}catch(e){document.getElementById('message').textContent='Server unavailable; retrying.'}}poll();setInterval(poll,5000)</script>'''

def command(args):
    try:return subprocess.check_output(args,stderr=subprocess.DEVNULL,text=True,timeout=2).strip()
    except (OSError,subprocess.SubprocessError):return 'unavailable (not guessed)'

def read_json(p,default):
    try:return json.loads(p.read_text())
    except (OSError,ValueError):return default

def health(port,path):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=.5) as r:return 'online' if r.status==200 else 'not ready'
    except Exception:return 'not ready'

MODELS = pathlib.Path('/srv/ai/models')
WAVE_NAMES = {'1': 'Wave 1 - first models and the Director LLM',
              '2': 'Wave 2 - image and edit models',
              '3': 'Wave 3 - motion models and LoRAs',
              '4': 'Wave 4 - opt-in large LLMs (sudo turin-enable-heavy-llms)'}


def director_port():
    try:
        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import gpu_policy as gp
        p = gp.profile(gp.active_profile_id()); return gp.launch_args(p)['port'], p['id']
    except Exception:
        return 8000, 'qwen36_35b_a3b_abliterated_q8'


def snapshot(models=MODELS, state=None):
    phase=read_json(state or STATE,{'phase':'firstboot','message':'Waiting for provisioning phase state'})
    doc=read_json(models/'download-status.json',{})
    if isinstance(doc,list):doc={'rows':doc}
    rows=doc.get('rows',[]);completed=0;total=0;waves={}
    for row in rows:
        size=int(row.get('size_bytes') or 0);total+=size;done=0
        if row.get('state')=='verified':done=size
        else:
            name=pathlib.PurePosixPath(row.get('destination',''))
            if not name.is_absolute() and '..' not in name.parts:
                try:done=min(size,pathlib.Path(models,str(name)+'.part').stat().st_size)
                except OSError:pass
        completed+=done
        w=waves.setdefault(str(row.get('wave',1)),{'name':'','files':0,'verified':0,'blocked':0,'skipped':0,'bytes_total':0,'bytes_done':0})
        w['files']+=1;w['bytes_total']+=size;w['bytes_done']+=done
        for k in ('verified','blocked','skipped'):
            if row.get('state')==k:w[k]+=1
    for k,w in waves.items():
        w['name']=WAVE_NAMES.get(k,'Wave '+k);w['percent']=round(100*w['bytes_done']/w['bytes_total'],1) if w['bytes_total'] else 0
    port,profile=director_port()
    # No HTML interpolation of logs or model names. Limit log read size.
    try:
        with open('/var/log/turin/provision.log','rb') as f:
            f.seek(0,2);f.seek(max(0,f.tell()-10000));log=f.read().decode(errors='replace')
    except OSError:log='Log not yet available'
    return {**phase,'services':{'Easy Studio :7860':health(7860,'/'),'ComfyUI GPU0 :8188':health(8188,'/system_stats'),'ComfyUI GPU1 :8189':health(8189,'/system_stats'),f'Director LLM :{port} ({profile})':health(port,'/health')},
      'ports':{'dashboard':8099,'easy_studio':7860,'comfy_gpu0':8188,'comfy_gpu1':8189,'director_llm':port,'vnc':5900},
      'telemetry':{'gpus':command(['nvidia-smi','--query-gpu=index,name,memory.total,memory.used,temperature.gpu,power.draw','--format=csv']),
       'cpu_sensors':command(['sensors','-j']),'fans_pump':'Unavailable until verified BMC header/tach mapping; no guessed pump reading',
       'memory_bytes':command(['free','-b']),'memory_channels':'4-channel population requires BIOS/physical/SMBIOS inspection; not inferred from total RAM',
       'tailscale_ipv4':command(['tailscale','ip','-4']),'health':read_json(pathlib.Path('/var/lib/turin/health.json'),{})},
      'waves':dict(sorted(waves.items())),'tokens_configured':doc.get('tokens',{}),'heavy_llms_enabled':doc.get('heavy_llms_enabled',False),
      'downloads':rows,'download_progress_percent':round(100*completed/total,1) if total else 0,'log':log}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/':body=HTML.encode();kind='text/html; charset=utf-8'
        elif self.path=='/api/status':body=json.dumps(snapshot()).encode();kind='application/json'
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'");self.end_headers();self.wfile.write(body)
    def do_POST(self):self.send_error(403,'Read-only dashboard. Credentials must not be submitted over HTTP.')
    def log_message(self,*args):pass

def self_test():
    s=ThreadingHTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=s.serve_forever,daemon=True);t.start();base=f'http://127.0.0.1:{s.server_port}'
    try:
        with urllib.request.urlopen(base+'/') as r:assert r.status==200 and b'EPYC Studio' in r.read()
        with urllib.request.urlopen(base+'/api/status') as r:d=json.load(r);assert 'services' in d and 'waves' in d and d['ports']['director_llm']==8000
        try:urllib.request.urlopen(urllib.request.Request(base+'/api/tokens',data=b'test'))
        except urllib.error.HTTPError as e:assert e.code==403
        else:raise AssertionError('Credential route unexpectedly writable')
        print('PASS: live HTML 200, JSON 200, unsafe token POST 403, telemetry absence handled')
    finally:s.shutdown();s.server_close();t.join()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8099);a=p.parse_args()
    if a.self_test:self_test()
    else:ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
