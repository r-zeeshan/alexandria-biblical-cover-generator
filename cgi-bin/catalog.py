#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = 'AIzaSyAY6XvPxrdS_fMNMZEUkJd7UW9b9yuJDgI'
SOURCE_FOLDER = '1ybFYDJk7Y3VlbsEjRAh1LOfdyVsHM_cS'
CACHE_FILE = Path(__file__).resolve().parent.parent / 'catalog_cache.json'
CACHE_MAX_AGE_SECONDS = 3600


def _print_headers():
    print('Content-Type: application/json')
    print('Access-Control-Allow-Origin: *')
    print('Access-Control-Allow-Methods: GET, POST, OPTIONS')
    print('Access-Control-Allow-Headers: Content-Type')
    print()


def _drive_list(params):
    base = 'https://www.googleapis.com/drive/v3/files'
    params = dict(params)
    params['key'] = API_KEY
    params['supportsAllDrives'] = 'true'
    params['includeItemsFromAllDrives'] = 'true'
    req = Request(f"{base}?{urlencode(params)}")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def sync_catalog():
    books = []
    page_token = ''
    pattern = re.compile(r'^(\d+)\.\s+(.+?)\s+[—\-]\s+(.+)$')

    while True:
        payload = _drive_list({
            'q': f"'{SOURCE_FOLDER}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            'fields': 'nextPageToken,files(id,name,modifiedTime)',
            'pageSize': 1000,
            'pageToken': page_token,
        })
        folders = payload.get('files', [])

        for folder in folders:
            name = str(folder.get('name', '')).strip()
            match = pattern.match(name)
            if not match:
                continue
            number = int(match.group(1))
            title = match.group(2).strip()
            author = match.group(3).strip()

            files_payload = _drive_list({
                'q': f"'{folder['id']}' in parents and trashed=false",
                'fields': 'files(id,name,mimeType)',
                'pageSize': 200,
            })
            cover = next((f for f in files_payload.get('files', []) if str(f.get('name', '')).lower().endswith(('.jpg', '.jpeg'))), None)

            books.append({
                'id': number,
                'number': number,
                'title': title,
                'author': author,
                'folder_name': name,
                'folder_id': folder.get('id'),
                'cover_jpg_id': cover.get('id') if cover else '',
                'cover_name': cover.get('name') if cover else '',
                'synced_at': datetime.now(timezone.utc).isoformat(),
            })

        page_token = payload.get('nextPageToken', '')
        if not page_token:
            break

    books.sort(key=lambda b: b.get('number', 0))
    data = {
        'books': books,
        'synced_at': datetime.now(timezone.utc).isoformat(),
        'count': len(books),
    }
    CACHE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return data


def _read_cache():
    if not CACHE_FILE.exists():
        return None
    return json.loads(CACHE_FILE.read_text(encoding='utf-8'))


def _cache_status():
    if not CACHE_FILE.exists():
        return {'cached': False, 'age_seconds': 0, 'count': 0, 'synced_at': None, 'stale': False}
    age = max(0.0, time.time() - CACHE_FILE.stat().st_mtime)
    payload = _read_cache() or {}
    return {
        'cached': True,
        'age_seconds': age,
        'count': len(payload.get('books', [])),
        'synced_at': payload.get('synced_at'),
        'stale': age > CACHE_MAX_AGE_SECONDS,
    }


def main():
    method = os.environ.get('REQUEST_METHOD', 'GET').upper()
    path_info = os.environ.get('PATH_INFO', '')
    _print_headers()

    try:
        if method == 'OPTIONS':
            print(json.dumps({'ok': True}))
            return
        if method == 'GET' and path_info in {'', '/'}:
            cache = _read_cache()
            print(json.dumps(cache if cache else sync_catalog()))
            return
        if method == 'POST' and path_info == '/refresh':
            print(json.dumps(sync_catalog()))
            return
        if method == 'GET' and path_info == '/status':
            print(json.dumps(_cache_status()))
            return
        print(json.dumps({'error': f'Unsupported route: {method} {path_info}'}))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))


if __name__ == '__main__':
    main()
