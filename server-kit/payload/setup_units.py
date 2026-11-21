#!/usr/bin/env python3
"""Write the AI systemd units. Ports are identical to the Session 2 pack (config/llm_models.json):
  8000 Director LLM (llama-server; card from placement.json: GPU 0 hybrid by default)   8188 ComfyUI GPU 0
  8189 ComfyUI GPU 1 (paused while a profile above 70 GB holds GPU 1)   7860 Easy Studio
  8099 status dashboard (turin-status-web, written by install_services.sh)   5900 VNC (setup_remote.sh)
Everything here listens on 127.0.0.1 only; the Mac reaches it through SSH LocalForward.
"""
import pathlib, sys
UNIT_DIR = pathlib.Path('/etc/systemd/system')
PORTS = {'director': 8000, 'comfy_gpu0': 8188, 'comfy_gpu1': 8189, 'easy_studio': 7860, 'dashboard': 8099, 'vnc': 5900}
COMMON_ENV = {
    'COMFY_URL': 'http://127.0.0.1:8188', 'COMFY_PRIMARY_URL': 'http://127.0.0.1:8188',
    'COMFY_SECONDARY_URL': 'http://127.0.0.1:8189', 'COMFY_PRIMARY_GPU': '0', 'COMFY_SECONDARY_GPU': '1',
    'LLM_BASE_URL': 'http://127.0.0.1:8000/v1', 'LLM_REMOTE_ENABLED': '0', 'GPU_VRAM_PLAN_GB': '88',
    'EASY_STUDIO_MODELS': '/srv/ai/models', 'HF_HOME': '/srv/ai/.cache/huggingface'}
COMFY = '/srv/ai/ComfyUI/.venv/bin/python /srv/ai/ComfyUI/main.py --listen 127.0.0.1 --port {port} --disable-auto-launch'
UNITS = {
    'turin-comfy0': dict(desc='ComfyUI GPU 0 :8188 (image lane, app/hardware_map.py)', wd='/srv/ai/ComfyUI', gpu='0',
                         cmd=COMFY.format(port=8188), after='turin-models.service'),
    'turin-comfy1': dict(desc='ComfyUI GPU 1 :8189 (video lane, app/hardware_map.py)', wd='/srv/ai/ComfyUI', gpu='1',
                         cmd=COMFY.format(port=8189), cond='/usr/bin/python3 /opt/turin/payload/gpu_policy.py --allow-comfy1'),
    'turin-director': dict(desc='Director LLM llama-server :8000 (card from placement.json; waits for SHA256-verified GGUF)', wd='/srv/ai', gpu='',
                           cmd='/usr/bin/python3 /opt/turin/payload/run_director.py'),
    'turin-easy-studio': dict(desc='Easy Studio :7860 (uvicorn server:app)', wd='/srv/ai/app', gpu='',
                              cmd='/usr/bin/python3 /opt/turin/payload/run_app.py', after='turin-comfy0.service turin-director.service'),
    'turin-models': dict(desc='Models: confirm the store copy, download only what is missing (SHA256, resumable)', wd='/srv/ai', gpu='',
                         cmd='/usr/bin/python3 /opt/turin/payload/model_downloader.py', restart_sec=300, umask='0022'),
}


def render(name, u):
    env = ''.join(f'Environment={k}={v}\n' for k, v in COMMON_ENV.items())
    if u['gpu']: env = f'Environment=CUDA_VISIBLE_DEVICES={u["gpu"]}\n' + env
    cond = f'ExecCondition={u["cond"]}\n' if u.get('cond') else ''
    after = ' ' + u['after'] if u.get('after') else ''
    return f'''[Unit]
Description={u["desc"]}
Wants=network-online.target
After=network-online.target{after}
StartLimitIntervalSec=0
[Service]
User=studio
Group=studio
WorkingDirectory={u["wd"]}
{env}{cond}ExecStart={u["cmd"]}
Restart=on-failure
RestartSec={u.get("restart_sec", 30)}
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=full
PrivateTmp=yes
UMask={u.get("umask", "0027")}
[Install]
WantedBy=multi-user.target
'''


def main(unit_dir=UNIT_DIR):
    unit_dir = pathlib.Path(unit_dir)
    for name, u in UNITS.items():
        (unit_dir / f'{name}.service').write_text(render(name, u))
    return sorted(UNITS)


if __name__ == '__main__':
    print('wrote', main(sys.argv[1] if len(sys.argv) > 1 else UNIT_DIR))
