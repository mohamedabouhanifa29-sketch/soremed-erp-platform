"""Tests d'intégration des principaux workflows CRUD et stock."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email":"test-admin@example.com", "password":"test-only-password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_crud_purchase_and_stock_workflow():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        headers = auth_headers(client)
        created_user = client.post("/api/v1/users", headers=headers, json={"full_name":"Test Achats", "email":f"achats-{suffix}@soremed.ma", "password":"Secret123!", "role":"achats"})
        assert created_user.status_code == 201, created_user.text
        user_id = created_user.json()["id"]
        assert "password" not in created_user.json() and "password_hash" not in created_user.json()
        duplicate_user = client.post("/api/v1/users", headers=headers, json={"full_name":"Doublon", "email":f"achats-{suffix}@soremed.ma", "password":"Secret123!", "role":"achats"})
        assert duplicate_user.status_code == 409 and "email" in duplicate_user.json()["detail"].lower()
        toggled = client.patch(f"/api/v1/users/{user_id}/status", headers=headers)
        assert toggled.status_code == 200 and toggled.json()["is_active"] is False

        created_client = client.post("/api/v1/clients", headers=headers, json={"name":f"Client {suffix}", "company_name":"SOREMED Test", "ice":suffix, "rc":"RC1", "address":"Adresse", "city":"Casablanca", "phone":"0600000000", "email":f"client-{suffix}@example.com", "status":"active"})
        assert created_client.status_code == 201, created_client.text
        client_id = created_client.json()["id"]

        created_product = client.post("/api/v1/products", headers=headers, json={"reference":f"REF-{suffix}", "name":"Produit test", "description":"Test", "price":10, "category_id":None, "stock":2, "minimum_stock":1, "barcode":f"BAR-{suffix}", "status":"active", "photo_path":None})
        assert created_product.status_code == 201, created_product.text
        product_id = created_product.json()["id"]
        assert created_product.json()["stock"] == 0
        adjusted = client.post("/api/v1/stock/movements", headers=headers, json={"product_id":product_id,"movement_type":"AJUSTEMENT_POSITIF","quantity":2,"reason":"Stock de test","comment":None})
        assert adjusted.status_code == 201 and adjusted.json()["movement_type"] == "AJUSTEMENT_POSITIF"

        supplier = client.post("/api/v1/suppliers", headers=headers, json={"name":f"Fournisseur {suffix}","company_name":"Approvisionnement Test","ice":f"SUP-{suffix}","rc":"RC-SUP","email":f"supplier-{suffix}@example.com","phone":"0500000000","address":"Zone industrielle","city":"Casablanca","primary_contact":"Responsable achats","status":"active"})
        assert supplier.status_code == 201, supplier.text
        supplier_id=supplier.json()["id"]

        purchase = client.post("/api/v1/purchases", headers=headers, json={"number":f"ACH-{suffix}", "supplier_id":supplier_id, "status":"ordered", "expected_delivery_date":"2026-08-05T00:00:00", "notes":None, "lines":[{"product_id":product_id, "quantity":3, "unit_price":10,"discount":0,"tax_rate":20}]})
        assert purchase.status_code == 201, purchase.text
        purchase_id = purchase.json()["id"]
        assert float(purchase.json()["total"]) == 36
        product = next(item for item in client.get("/api/v1/products", headers=headers).json() if item["id"] == product_id)
        assert product["stock"] == 2

        edited = client.put(f"/api/v1/purchases/{purchase_id}", headers=headers, json={"number":f"ACH-{suffix}", "supplier_id":supplier_id, "status":"awaiting_receipt", "expected_delivery_date":"2026-08-05T00:00:00", "notes":"Modifié", "lines":[{"product_id":product_id, "quantity":4, "unit_price":9,"discount":0,"tax_rate":0}]})
        assert edited.status_code == 200 and float(edited.json()["total"]) == 36
        received=client.patch(f"/api/v1/purchases/{purchase_id}/receive",headers=headers)
        assert received.status_code==200 and received.json()["status"]=="RECEPTIONNEE"
        assert client.patch(f"/api/v1/purchases/{purchase_id}/receive",headers=headers).status_code==409
        product = next(item for item in client.get("/api/v1/products", headers=headers).json() if item["id"] == product_id)
        assert product["stock"] == 6
        movements=client.get("/api/v1/stock/movements",headers=headers).json()
        assert any(x["reference"]==f"ACH-{suffix}" and x["movement_type"]=="ENTREE_ACHAT" and x["previous_stock"]==2 and x["new_stock"]==6 for x in movements)

        assert client.delete(f"/api/v1/clients/{client_id}", headers=headers).status_code == 204
        assert client.delete(f"/api/v1/users/{user_id}", headers=headers).status_code == 204


def test_admin_cannot_delete_self_and_reports_download():
    with TestClient(app) as client:
        headers = auth_headers(client)
        me = client.get("/api/v1/auth/me", headers=headers).json()
        response = client.delete(f"/api/v1/users/{me['id']}", headers=headers)
        assert response.status_code == 400
        for path in ("stock.xlsx", "clients.xlsx", "purchases.xlsx", "stock.pdf"):
            report = client.get(f"/api/v1/reports/{path}", headers=headers)
            assert report.status_code == 200 and len(report.content) > 0
        backup = client.get("/api/v1/settings/backup", headers=headers)
        assert backup.status_code == 200 and len(backup.content) > 100
        restored = client.post("/api/v1/settings/restore", headers=headers, files={"backup":("soremed-test.db", backup.content, "application/x-sqlite3")})
        assert restored.status_code == 200, restored.text
