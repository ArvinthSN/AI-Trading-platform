from fastapi.testclient import TestClient

from app.core.auth import AuthenticatedUser, get_current_user
from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_global_regions_are_explicitly_unavailable_without_provider() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/global/regions")
    assert response.status_code == 200
    data = response.json()
    assert {region["id"] for region in data["regions"]} == {
        "americas",
        "europe",
        "asia-pacific",
        "middle-east-africa",
    }
    assert all(region["data_status"] == "unavailable" for region in data["regions"])


def test_watchlists_remain_unavailable_without_auth_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/market/watchlists")
    assert response.status_code == 503
    assert "Authentication provider" in response.json()["detail"]


def test_agent_dashboard_is_explicitly_unavailable_without_postgres() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("test-user")
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/agents/dashboard")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "PostgreSQL is not configured" in response.json()["detail"]


def test_scenario_simulation_does_not_create_fake_results() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("test-user")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/agents/simulations",
                json={
                    "kind": "scenario",
                    "symbol": "BTCUSDT",
                    "parameters": {"shock_percent": -10},
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "No simulated result was created" in response.json()["detail"]


def test_portfolio_sources_require_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/portfolio/sources")
    assert response.status_code == 503
    assert "Authentication provider" in response.json()["detail"]


def test_portfolio_binance_summary_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/portfolio/summary?source=binance")
    assert response.status_code == 503
    assert "Authentication provider" in response.json()["detail"]


def test_portfolio_sources_report_unconfigured_providers_without_fake_data() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("test-user")
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/portfolio/sources")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "read_only"
    assert payload["sources"] == [
        {"id": "paper", "label": "Paper Trading", "configured": False},
        {"id": "binance", "label": "Binance Spot", "configured": False},
    ]


def test_binance_portfolio_summary_is_unavailable_without_server_credentials() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("test-user")
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/portfolio/summary?source=binance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "credentials are not configured" in response.json()["detail"]


def test_portfolio_rejects_unknown_source() -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("test-user")
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/portfolio/summary?source=live")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
