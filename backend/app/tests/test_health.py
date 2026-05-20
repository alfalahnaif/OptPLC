from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "plc-agent-optimizer-api"
    assert body["version"] == "0.1.0"
    assert "timestamp" in body

