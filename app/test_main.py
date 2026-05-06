import sys
from unittest.mock import MagicMock, patch

sys.modules['psycopg2'] = MagicMock()
sys.modules['redis'] = MagicMock()
sys.modules['prometheus_fastapi_instrumentator'] = MagicMock()

with patch('psycopg2.connect'), patch('redis.from_url'):
    from main import app

from fastapi.testclient import TestClient
client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "SA Clinic Appointment API"

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
