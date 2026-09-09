"""本地连接配置持久化（~/.hxssh.json）。"""
from __future__ import annotations

import json
from pathlib import Path

CFG_PATH = Path.home() / '.hxssh.json'

DEFAULTS = {
    'host': '',
    'port': 22,
    'username': 'root',
    'auth': 'password',
    'password': '',
    'key_path': '',
    'key_pass': '',
    'remember': False,
    'interval': 2,
}


def load():
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(CFG_PATH.read_text('utf-8'))
        if isinstance(data, dict):
            cfg.update({k: data[k] for k in DEFAULTS if k in data})
    except Exception:
        pass
    return cfg


def save(cfg):
    data = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    if not data.get('remember'):
        data['password'] = ''
        data['key_pass'] = ''
    try:
        CFG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
    except Exception:
        pass
