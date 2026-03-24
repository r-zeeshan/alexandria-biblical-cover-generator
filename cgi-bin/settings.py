#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / 'settings_store.json'


def _print_headers():
    print('Content-Type: application/json')
    print('Access-Control-Allow-Origin: *')
    print('Access-Control-Allow-Methods: GET, POST, OPTIONS')
    print('Access-Control-Allow-Headers: Content-Type')
    print()


def _read_store():
    if not STORE.exists():
        return {}
    return json.loads(STORE.read_text(encoding='utf-8'))


def _write_store(payload):
    STORE.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def main():
    method = os.environ.get('REQUEST_METHOD', 'GET').upper()
    path_info = os.environ.get('PATH_INFO', '')
    _print_headers()

    try:
        if method == 'OPTIONS':
            print(json.dumps({'ok': True}))
            return
        if method == 'GET' and path_info in {'', '/'}:
            print(json.dumps(_read_store()))
            return
        if method == 'POST' and path_info in {'', '/'}:
            length = int(os.environ.get('CONTENT_LENGTH') or '0')
            body = sys.stdin.read(length) if length else '{}'
            incoming = json.loads(body or '{}')
            current = _read_store()
            current.update(incoming)
            _write_store(current)
            print(json.dumps(current))
            return
        if method == 'POST' and path_info == '/reset':
            if STORE.exists():
                STORE.unlink()
            print(json.dumps({'status': 'reset'}))
            return
        print(json.dumps({'error': f'Unsupported route: {method} {path_info}'}))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))


if __name__ == '__main__':
    main()
