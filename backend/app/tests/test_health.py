from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["matiec"] in {"available", "unavailable"}
    assert "matiec_path" in body
    assert body["llm_provider"]
    assert "timestamp" in body
