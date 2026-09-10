from pathlib import Path


def test_api_image_uses_validated_python_constraints():
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / 'deploy/Dockerfile.api').read_text(encoding='utf-8')
    assert 'COPY backend/constraints-py312.txt /app/backend/constraints-py312.txt' in dockerfile
    assert '-r /app/backend/requirements.txt -c /app/backend/constraints-py312.txt' in dockerfile
    assert 'python -m pip check' in dockerfile
    assert 'pip==26.2.1' in dockerfile
