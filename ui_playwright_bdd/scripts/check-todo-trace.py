"""Summarize only task POST status and text lengths from an existing local trace."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import zipfile

root = Path(__file__).resolve().parent.parent
run_id = sys.argv[1]
if not run_id or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for ch in run_id):
    raise SystemExit('Invalid run ID')
records = []
for file in (root / 'allure-runs' / run_id / 'results').glob('*.zip'):
    with zipfile.ZipFile(file) as archive:
        for name in archive.namelist():
            if not name.endswith('.network'):
                continue
            for line in archive.read(name).splitlines():
                event = json.loads(line)
                snapshot = event.get('snapshot', {})
                request = snapshot.get('request', {})
                route = urlsplit(request.get('url', '')).path
                if request.get('method') != 'POST' or not any(part in route.lower() for part in ('todo', 'task')):
                    continue
                post = request.get('postData', {})
                raw = post.get('text')
                if not raw and post.get('_sha1'):
                    resource = 'resources/' + post['_sha1']
                    if resource in archive.namelist():
                        raw = archive.read(resource).decode('utf-8')
                lengths = {}
                try:
                    body = json.loads(raw or '{}')
                    lengths = {key: len(value) for key, value in body.items()
                               if key in {'item', 'title', 'text', 'name'} and isinstance(value, str)}
                except (ValueError, AttributeError):
                    pass
                records.append({'method': 'POST', 'path': route,
                                'status': snapshot.get('response', {}).get('status'), 'textLengths': lengths})
print(json.dumps({'runId': run_id, 'taskRequests': records}, indent=2))
