"""Serve the frontend and proxy /api requests to the local development API."""

from http.client import HTTPConnection
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
API_HOST = "127.0.0.1"
API_PORT = 8001
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def _proxy_api(self):
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(content_length) if content_length else None
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS and name.lower() != "host"
        }
        headers["Host"] = f"{API_HOST}:{API_PORT}"

        connection = HTTPConnection(API_HOST, API_PORT, timeout=120)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in HOP_BY_HOP_HEADERS and name.lower() != "content-length":
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except OSError as error:
            payload = f'{{"detail":"Local API unavailable: {error}"}}'.encode("utf-8")
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
    server = ThreadingHTTPServer(("0.0.0.0", 8080), DevelopmentHandler)
    print("BOTEN local site: http://0.0.0.0:8080", flush=True)
    server.serve_forever()
