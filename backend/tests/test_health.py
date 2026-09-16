"""Test de non-régression du point de supervision."""
from fastapi.testclient import TestClient
from app.main import app
def test_health():
    with TestClient(app) as client:
        response=client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_login_and_protected_dashboard():
    """Le compte initial reçoit un JWT utilisable sur une route protégée."""
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"email": "test-admin@example.com", "password": "test-only-password"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        dashboard = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert dashboard.status_code == 200
        assert "products_count" in dashboard.json()
