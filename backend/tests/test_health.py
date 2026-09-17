"""健康检查测试（pytest，阶段 0 用）。

运行：cd backend && python -m pytest
"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
