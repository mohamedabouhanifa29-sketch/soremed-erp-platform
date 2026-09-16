"""Présence et idempotence des fournisseurs de démonstration."""
from fastapi.testclient import TestClient
from app.main import app
from app.services.demo_suppliers import DEMO_SUPPLIERS

def test_demo_suppliers_are_active_available_and_unique():
    with TestClient(app) as client:
        login=client.post("/api/v1/auth/login",json={"email":"test-admin@example.com","password":"test-only-password"})
        headers={"Authorization":f"Bearer {login.json()['access_token']}"}
        response=client.get("/api/v1/suppliers",headers=headers,params={"status":"active"})
        assert response.status_code==200
        by_ice={supplier["ice"]:supplier for supplier in response.json()}
        for expected in DEMO_SUPPLIERS:
            assert expected["ice"] in by_ice
            assert by_ice[expected["ice"]]["name"]==expected["name"]
            assert by_ice[expected["ice"]]["status"]=="active"
    with TestClient(app) as restarted:
        token=restarted.post("/api/v1/auth/login",json={"email":"test-admin@example.com","password":"test-only-password"}).json()["access_token"]
        rows=restarted.get("/api/v1/suppliers",headers={"Authorization":f"Bearer {token}"}).json()
        expected_ices={item["ice"] for item in DEMO_SUPPLIERS}
        assert len([supplier for supplier in rows if supplier["ice"] in expected_ices])==5
