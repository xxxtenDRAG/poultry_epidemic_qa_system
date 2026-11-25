"""全链路溯源阶段字典测试（不依赖 MySQL）。"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_traceability_stages():
    resp = client.get("/api/traceability/stages")
    assert resp.status_code == 200
    stages = resp.json()
    assert [item["key"] for item in stages] == [
        "incubation",
        "brooding",
        "growing",
        "health",
        "outbound",
        "slaughter",
        "quality",
        "coldchain",
        "sales",
    ]
    assert all(item["name"] and item["color"] for item in stages)
