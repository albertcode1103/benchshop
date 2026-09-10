"""Read-only same-origin checks after a Web/API deployment."""
import argparse
import json
from urllib.error import HTTPError
from urllib.request import urlopen


def check(base):
    failures = []
    checks = [('/', 'html'), ('/api/v1/ready', 'ready'),
              ('/api/v1/products', 'products'), ('/tb/site/BOTEN.png', 'image')]
    checks += [(path, 'blocked') for path in ('/tb/pricelist.xlsx', '/tb/HarmonyOS+Sans.zip',
                                             '/backend/boten.db', '/backend/main.py', '/.env')]
    for path, kind in checks:
        try:
            with urlopen(base.rstrip('/') + path, timeout=15) as response:
                status = response.status
                body = response.read(4 * 1024 * 1024)
                content_type = response.headers.get('Content-Type', '')
            valid = status == 200
            if kind == 'blocked':
                valid = False
            elif kind == 'html':
                valid = valid and 'text/html' in content_type and b'<html' in body.lower()
            elif kind == 'ready':
                valid = valid and json.loads(body).get('status') == 'ready'
            elif kind == 'products':
                data = json.loads(body)
                items = data.get('items') if isinstance(data, dict) else None
                valid = (valid and isinstance(items, list) and bool(items)
                         and all(isinstance(item, dict) and item.get('id') for item in items))
            elif kind == 'image':
                valid = valid and body.startswith(b'\x89PNG\r\n\x1a\n')
        except HTTPError as error:
            valid = kind == 'blocked' and error.code in (403, 404)
        except Exception:
            valid = False
        print(('PASS' if valid else 'FAIL') + ' ' + path)
        if not valid:
            failures.append(path)
    return not failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url', help='Same-origin Web URL, e.g. http://192.168.31.69:8080')
    args = parser.parse_args()
    raise SystemExit(0 if check(args.base_url) else 1)
