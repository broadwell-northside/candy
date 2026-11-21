#!/usr/bin/env python3
"""turin-easy-studio.service: exec the verified Easy Studio entrypoint (PR #41, app/server.py -> FastAPI `app`).

    PYTHONPATH=/srv/ai/app:/srv/ai/app/app /srv/ai/app/.venv/bin/python -m uvicorn server:app \
        --app-dir /srv/ai/app/app --host 127.0.0.1 --port 7860
"""
import json, os, pathlib
APP = '/srv/ai/app'
DEFAULT_START = [APP + '/.venv/bin/python', '-m', 'uvicorn', 'server:app', '--app-dir', APP + '/app',
                 '--host', '127.0.0.1', '--port', '7860']
DEFAULT_ENV = {'PYTHONPATH': APP + ':' + APP + '/app'}


def build(c):
    argv = c.get('app_start') or DEFAULT_START  # PR #41's entrypoint unless install.json says otherwise
    env = dict(os.environ)
    env.update(c.get('app_env') or {})
    # Loopback only. EASY_STUDIO_* are what app/server.py reads; HOST/PORT kept for other entrypoints.
    env.update(EASY_STUDIO_HOST='127.0.0.1', EASY_STUDIO_PORT='7860', HOST='127.0.0.1', PORT='7860',
               EASY_STUDIO_OUTPUTS=APP + '/outputs', COMFY_DIR='/srv/ai/ComfyUI',
               COMFY_PYTHON='/srv/ai/ComfyUI/.venv/bin/python', LLM_MODELS_FILE=APP + '/config/llm_models.json')
    if '--host' in argv and argv[argv.index('--host') + 1] != '127.0.0.1': raise SystemExit('Easy Studio must bind 127.0.0.1')
    return argv, env


if __name__ == '__main__':
    argv, env = build(json.loads(pathlib.Path('/opt/turin/config/install.json').read_text()))
    os.execvpe(argv[0], argv, env)
