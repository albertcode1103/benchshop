import unittest
from backend.payload_bounds import validate_tree


class PayloadBoundsTests(unittest.TestCase):
    def test_rejects_deep_or_large_input(self):
        nested = {}
        for _ in range(14):
            nested = {"child": nested}
        for value in (nested, list(range(1001)), {"text": "a" * 10001}, {str(i): i for i in range(257)}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                validate_tree(value)

    def test_normal_payload_preserved(self):
        value = {"items": [{"code": "BTK-1016", "quantity": 2, "name": "卡套"}], "selections": {"motor": ["m1"]}}
        self.assertIs(value, validate_tree(value))
