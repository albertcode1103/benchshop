"""Shared limits for nested commerce JSON payloads."""
import math
def validate_tree(value):
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 12 or nodes > 50000:
            raise ValueError("Business payload is too deeply nested or too large")
        if isinstance(item, dict):
            if len(item) > 256:
                raise ValueError("Too many object fields")
            if any(len(str(key)) > 200 for key in item):
                raise ValueError("Field name is too long")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > 1000:
                raise ValueError("Too many list entries")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str) and len(item) > 10000:
            raise ValueError("Text exceeds 10000 characters")
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Numeric values must be finite")
    return value
