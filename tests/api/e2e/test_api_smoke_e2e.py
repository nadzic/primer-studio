import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.e2e
def test_health_and_model_endpoints_smoke(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import health as health_route

    async def _ok_check() -> health_route.DependencyCheck:
        return health_route.DependencyCheck(status="ok", latency_ms=1.0)

    monkeypatch.setattr(health_route, "_check_llm", _ok_check)
    monkeypatch.setenv("LLM_MODEL_NAME", "test-model")
    client = TestClient(app)

    health_response = client.get("/api/v1/health")
    model_response = client.get("/api/v1/meta/model")

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert model_response.status_code == 200
    assert model_response.json() == {"model": "test-model"}
