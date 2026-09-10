import asyncio
import unittest
from backend.request_limits import RequestSizeLimit


class RequestLimitTests(unittest.TestCase):
    def test_invalid_declared_lengths_and_disconnect(self):
        async def run(headers, message, expected_status):
            called, sent = [], []
            async def app(scope, receive, send):
                called.append(True)
            async def receive():
                return message
            async def send(value):
                sent.append(value)
            await RequestSizeLimit(app, max_bytes=5)({"type": "http", "headers": headers}, receive, send)
            self.assertFalse(called)
            if expected_status is None:
                self.assertEqual([], sent)
            else:
                self.assertEqual(expected_status, sent[0]["status"])
        for declared, expected in ((b"-1", 400), (b"invalid", 400), (b"6", 413), (b"1", 413)):
            asyncio.run(run([(b"content-length", declared)],
                            {"type": "http.request", "body": b"123456", "more_body": False}, expected))
        asyncio.run(run([], {"type": "http.disconnect"}, None))

    def test_chunked_overflow_never_reaches_application(self):
        async def run():
            called = []
            sent = []
            chunks = iter([{"type": "http.request", "body": b"abc", "more_body": True},
                           {"type": "http.request", "body": b"def", "more_body": False}])
            async def app(scope, receive, send):
                called.append(True)
            async def receive():
                return next(chunks)
            async def send(message):
                sent.append(message)
            await RequestSizeLimit(app, max_bytes=5)({"type": "http", "headers": []}, receive, send)
            self.assertFalse(called)
            self.assertEqual(413, sent[0]["status"])
        asyncio.run(run())

    def test_body_is_preserved_at_limit(self):
        async def run():
            async def receive():
                return {"type": "http.request", "body": b"abc", "more_body": False}
            async def app(scope, replay, send):
                self.assertEqual(b"abc", (await replay())["body"])
            await RequestSizeLimit(app, max_bytes=3)({"type": "http", "headers": []}, receive, None)
        asyncio.run(run())
