from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from unittest.mock import patch
from deploy.local_dev_server import DevelopmentHandler


def test_local_proxy_bounds_and_forwarded_headers():
    server = ThreadingHTTPServer(('127.0.0.1', 0), DevelopmentHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch('deploy.local_dev_server.HTTPConnection') as upstream:
            for headers, expected in [({'Content-Length': '10485761'}, 413),
                                      ({'Content-Length': '-1'}, 413),
                                      ({'Content-Length': 'invalid'}, 400),
                                      ({'Transfer-Encoding': 'chunked'}, 400)]:
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                connection.request('POST', '/api/v1/test', headers=headers)
                response = connection.getresponse()
                assert response.status == expected
                response.read()
                connection.close()
            upstream.assert_not_called()
            result = upstream.return_value.getresponse.return_value
            result.status, result.reason = 200, 'OK'
            result.read.return_value = b'{}'
            result.getheaders.return_value = [('Content-Type', 'application/json')]
            connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            connection.request('POST', '/api/v1/test', body=b'{}', headers={
                'Forwarded': 'for=attacker', 'X-Forwarded-For': 'attacker',
                'X-Forwarded-Proto': 'https', 'X-Real-IP': 'attacker',
                'Content-Type': 'application/json'})
            response = connection.getresponse()
            assert response.status == 200
            response.read()
            connection.close()
            forwarded = upstream.return_value.request.call_args.kwargs['headers']
            assert forwarded['X-Forwarded-For'] == '127.0.0.1'
            assert forwarded['X-Forwarded-Proto'] == 'http'
            assert not {'forwarded', 'x-real-ip'} & {key.lower() for key in forwarded}
            assert upstream.return_value.request.call_args.kwargs['body'] == b'{}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_local_server_only_publishes_browser_assets():
    server = ThreadingHTTPServer(('127.0.0.1', 0), DevelopmentHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for path, expected in [('/', 200), ('/admin/', 200), ('/tb/site/BOTEN.png', 200),
                               ('/backend/boten.db', 404), ('/.git/config', 404),
                               ('/tb/pricelist.xlsx', 404), ('/docs/', 404), ('/tb/', 404)]:
            connection = HTTPConnection('127.0.0.1', server.server_port)
            connection.request('HEAD', path)
            response = connection.getresponse()
            assert response.status == expected, path
            response.read()
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
