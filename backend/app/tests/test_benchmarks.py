from fastapi.testclient import TestClient

from app.services.benchmark_runner import BenchmarkRunner


def test_get_benchmark_cases_returns_seed_cases(client: TestClient) -> None:
    response = client.get("/api/benchmarks/cases")
    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 5
    case_ids = {item["id"] for item in cases}
    assert case_ids == {"B001", "B002", "B003", "B004", "B005"}


def test_post_run_executes_single_case_by_mode(client: TestClient) -> None:
    response = client.post("/api/benchmarks/run", json={"caseId": "B001", "mode": "rule_based"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["caseId"] == "B001"
    assert payload["mode"] == "rule_based"
    assert "metrics" in payload
    assert "generationTimeMs" in payload


def test_compare_runs_all_modes(client: TestClient) -> None:
    response = client.post("/api/benchmarks/compare", json={"caseId": "B001"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["caseId"] == "B001"
    assert "rule_based" in payload["results"]
    assert "llm" in payload["results"]
    assert "llm_rag" in payload["results"]
    assert "comparison" in payload


def test_one_failed_mode_does_not_stop_comparison(client: TestClient, monkeypatch) -> None:
    original_load_cases = BenchmarkRunner._load_cases

    def _patched_load_cases(self: BenchmarkRunner):
        cases = original_load_cases(self)
        first = cases[0].model_copy(update={"requirement": "   "})
        return [first, *cases[1:]]

    monkeypatch.setattr(BenchmarkRunner, "_load_cases", _patched_load_cases)
    response = client.post("/api/benchmarks/compare", json={"caseId": "B001"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]["rule_based"]["error"] is not None


def test_benchmark_results_endpoint_returns_grouped_payload(client: TestClient) -> None:
    run_response = client.post("/api/benchmarks/run", json={"caseId": "B001", "mode": "llm"})
    assert run_response.status_code == 200
    response = client.get("/api/benchmarks/results")
    assert response.status_code == 200
    grouped = response.json()
    assert "B001" in grouped
    assert "llm" in grouped["B001"]


def test_benchmark_summary_values_are_numeric(client: TestClient) -> None:
    client.post("/api/benchmarks/run", json={"caseId": "B001", "mode": "rule_based"})
    client.post("/api/benchmarks/run", json={"caseId": "B001", "mode": "llm"})
    client.post("/api/benchmarks/run", json={"caseId": "B001", "mode": "llm_rag"})
    response = client.get("/api/benchmarks/summary")
    assert response.status_code == 200
    summary = response.json()
    assert isinstance(summary["totalRuns"], int)
    assert isinstance(summary["byMode"]["rule_based"]["avgLoc"], (int, float))
    assert isinstance(summary["byMode"]["llm"]["verificationRate"], (int, float))
