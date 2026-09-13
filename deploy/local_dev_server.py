"""Local frontend: NAS upstream by default; explicit isolated loopback mode."""

from http.client import HTTPConnection
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
from io import BytesIO


PROJECT_DIR = Path(__file__).resolve().parents[1]
API_HOST = "192.168.31.69"
API_PORT = 8080
MODE = 'nas'
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class DevelopmentHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-BenchShop-Upstream', MODE)
        super().end_headers()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def send_head(self):
        path = Path(self.translate_path(self.path)).resolve()
        try:
            relative = path.relative_to(PROJECT_DIR.resolve())
        except ValueError:
            self.send_error(404)
            return None
        if path.is_dir():
            path = (path / 'index.html').resolve()
        if not path.is_relative_to(PROJECT_DIR.resolve()):
            self.send_error(404)
            return None
        allowed_roots = {'admin', 'account', 'css', 'js', 'assets', 'tb'}
        allowed_extensions = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp',
                              '.svg', '.ico', '.woff', '.woff2', '.ttf', '.otf'}
        if (any(part.startswith('.') for part in relative.parts)
                or (relative.parts and relative.parts[0] not in allowed_roots and str(relative) != 'index.html')
                or path.suffix.lower() not in allowed_extensions or not path.is_file()):
            self.send_error(404)
            return None
        if path.suffix == '.html':
            label = 'NAS 正式数据 · 可写 / NAS LIVE · WRITABLE' if MODE == 'nas' else '本机隔离模式 / LOCAL TEST'
            banner = ('<div role="status" style="position:fixed;bottom:0;left:0;right:0;z-index:2147483647;'
                      'background:#7f1d1d;color:white;font:12px/24px sans-serif;text-align:center;pointer-events:none">'
                      + label + '</div>')
            raw = path.read_text(encoding='utf-8').replace('</body>', banner + '</body>').encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            return BytesIO(raw)
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None

    def _proxy_api(self):
        if not self.path.startswith('/api/'):
            self.send_error(404)
            return
        # Do not let arbitrary websites use this authenticated local bridge.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            self.send_error(403, 'Cross-origin proxy request rejected')
            return
        if self.headers.get('Transfer-Encoding'):
            self.send_error(400, 'Transfer encoding unsupported by local proxy')
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            self.send_error(400)
            return
        if content_length < 0 or content_length > 10 * 1024 * 1024:
            self.send_error(413)
            return
        body = self.rfile.read(content_length) if content_length else None
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS
            and name.lower() not in {'host', 'forwarded', 'x-forwarded-for', 'x-forwarded-proto', 'x-real-ip', 'x-forwarded-host'}
        }
        headers["Host"] = f"{API_HOST}:{API_PORT}"
        headers['X-Forwarded-For'] = self.client_address[0]
        headers['X-Forwarded-Proto'] = 'http'

        connection = HTTPConnection(API_HOST, API_PORT, timeout=120)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in HOP_BY_HOP_HEADERS and name.lower() not in {'content-length', 'cache-control'}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except OSError:
            payload = json.dumps({'detail': f'{MODE} API unavailable; no fallback or automatic retry'}).encode('utf-8')
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        finally:
            connection.close()

    def _dispatch(self):
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            super().do_GET()

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        if self.path.startswith("/api/"):
            self._proxy_api()
        else:
            super().do_HEAD()

    def do_POST(self):
        self._proxy_api()

    def do_PUT(self):
        self._proxy_api()

    def do_PATCH(self):
        self._proxy_api()

    def do_DELETE(self):
        self._proxy_api()

    def do_OPTIONS(self):
        self._proxy_api()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['nas', 'isolated'], default='nas')
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int)
    parser.add_argument('--api-port', type=int,
                        help='Loopback API port to proxy (default: 8001)')
    args = parser.parse_args()
    MODE = args.mode
    if args.api_port is not None:
        MODE = 'isolated'  # Backward-compatible explicit test port never targets NAS.
    API_HOST = '192.168.31.69' if MODE == 'nas' else '127.0.0.1'
    API_PORT = 8080 if MODE == 'nas' else (args.api_port or 8001)
    port = args.port or (8082 if MODE == 'nas' else 8081)
    if MODE == 'nas' and port == 8081:
        parser.error('8081 is reserved for isolated storage; use 8082 for NAS')
    server = ThreadingHTTPServer((args.bind, port), DevelopmentHandler)
    print(f'BOTEN {MODE}: http://{args.bind}:{port} -> http://{API_HOST}:{API_PORT} (no fallback)', flush=True)
    server.serve_forever()
