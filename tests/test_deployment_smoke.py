from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch
from deploy.smoke import check


class Response(BytesIO):
    status = 200
    def __init__(self, body, kind):
        super().__init__(body)
        self.headers = {'Content-Type': kind}


def responder(url, timeout=15):
    if url.endswith('/api/v1/ready'):
        return Response(b'{"status":"ready"}', 'application/json')
    if url.endswith('/api/v1/products'):
        return Response(b'{"items":[{"id":"device"}]}', 'application/json')
    if url.endswith('/tb/site/BOTEN.png'):
        return Response(b'\x89PNG\r\n\x1a\n', 'image/png')
    if url == 'http://test/':
        return Response(b'<html></html>', 'text/html')
    raise HTTPError(url, 404, 'Not found', {}, None)


def test_smoke_accepts_valid_deployment():
    with patch('deploy.smoke.urlopen', responder):
        assert check('http://test')


def test_smoke_rejects_error_json_and_public_source():
    def broken(url, timeout=15):
        if url.endswith('/api/v1/products'):
            return Response(b'{"error":"database unavailable"}', 'application/json')
        if url.endswith('.xlsx'):
            return Response(b'private source', 'application/octet-stream')
        return responder(url, timeout)
    with patch('deploy.smoke.urlopen', broken):
        assert not check('http://test')
