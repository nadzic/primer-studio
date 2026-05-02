import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_registered_api_routes(app: FastAPI) -> None:
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/health" in route_paths
    assert "/api/v1/meta/model" in route_paths
    assert "/api/v1/research" in route_paths


@pytest.mark.integration
def test_health_endpoint_via_testclient(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import health as health_route

    async def _ok_check() -> health_route.DependencyCheck:
        return health_route.DependencyCheck(status="ok", latency_ms=1.0)

    monkeypatch.setattr(health_route, "_check_llm", _ok_check)

    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert set(response.json()["checks"].keys()) == {"llm"}
