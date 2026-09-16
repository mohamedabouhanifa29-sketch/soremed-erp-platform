"""Workflow de validation des commandes par les rôles Achats et Admin."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email":email,"password":password})
    assert response.status_code == 200, response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


def test_order_approval_permissions_stock_and_isolation():
    suffix=uuid4().hex[:8]
    with TestClient(app) as client:
        admin=login(client,"test-admin@example.com","test-only-password")
        buyer_email=f"achats-{suffix}@example.com"
        assert client.post("/api/v1/users",headers=admin,json={"full_name":"Service Achats","email":buyer_email,"password":"Achats123!","role":"achats"}).status_code==201
        buyer=login(client,buyer_email,"Achats123!")

        def client_account(number:int):
            email=f"order-client-{number}-{suffix}@example.com"
            created=client.post("/api/v1/users",headers=admin,json={"full_name":f"Client Commande {number}","email":email,"password":"Client123!","role":"client"})
            assert created.status_code==201,created.text
            return login(client,email,"Client123!")

        first,second=client_account(1),client_account(2)
        product=client.post("/api/v1/products",headers=admin,json={"reference":f"ORD-{suffix}","name":"Produit validation","description":None,"price":40,"photo_path":None,"category_id":None,"stock":20,"minimum_stock":2,"barcode":None,"status":"active"}).json()
        product2=client.post("/api/v1/products",headers=admin,json={"reference":f"SUP-{suffix}","name":"Produit approvisionnement","description":None,"price":15,"photo_path":None,"category_id":None,"stock":4,"minimum_stock":1,"barcode":None,"status":"active"}).json()
        assert product["stock"] == 0 and product2["stock"] == 0
        assert client.post("/api/v1/stock/movements",headers=admin,json={"product_id":product["id"],"movement_type":"AJUSTEMENT_POSITIF","quantity":20,"reason":"Stock de test"}).status_code==201
        assert client.post("/api/v1/stock/movements",headers=admin,json={"product_id":product2["id"],"movement_type":"AJUSTEMENT_POSITIF","quantity":4,"reason":"Stock de test"}).status_code==201
        supplier=client.post("/api/v1/suppliers",headers=admin,json={"name":"Fournisseur workflow","company_name":"Distribution Test","ice":f"F-{suffix}","rc":None,"email":None,"phone":None,"address":None,"city":None,"primary_contact":None,"status":"active"}).json()
        supplier_purchase=client.post("/api/v1/purchases",headers=buyer,json={"number":f"ACH-W-{suffix}","supplier_id":supplier["id"],"status":"awaiting_receipt","expected_delivery_date":"2026-08-05T00:00:00","notes":None,"lines":[{"product_id":product["id"],"quantity":2,"unit_price":30,"discount":5,"tax_rate":20},{"product_id":product2["id"],"quantity":3,"unit_price":12,"discount":0,"tax_rate":0}]})
        assert supplier_purchase.status_code==201,supplier_purchase.text
        assert next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product2["id"])["stock"]==4
        assert client.post("/api/v1/purchases",headers=first,json={"supplier_id":supplier["id"],"lines":[{"product_id":product2["id"],"quantity":1,"unit_price":1}]}).status_code==403
        received=client.patch(f"/api/v1/purchases/{supplier_purchase.json()['id']}/receive",headers=buyer)
        assert received.status_code==200,received.text
        assert client.patch(f"/api/v1/purchases/{supplier_purchase.json()['id']}/receive",headers=buyer).status_code==409
        assert next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product2["id"])["stock"]==7

        created=client.post("/api/v1/client/orders",headers=first,json={"lines":[{"product_id":product["id"],"quantity":3}]})
        assert created.status_code==201,created.text
        order=created.json();assert order["status"]=="pending" and order["user_id"]
        assert next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product["id"])["stock"]==22
        assert client.patch(f"/api/v1/orders/{order['id']}/approve",headers=first,json={}).status_code==403
        assert client.get("/api/v1/orders",headers=first).status_code==403

        approved=client.patch(f"/api/v1/orders/{order['id']}/approve",headers=buyer,json={"comment":"Commande conforme"})
        assert approved.status_code==200,approved.text
        assert approved.json()["status"]=="approved"
        assert next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product["id"])["stock"]==19
        assert client.patch(f"/api/v1/orders/{order['id']}/approve",headers=buyer,json={}).status_code==409

        admin_order=client.post("/api/v1/client/orders",headers=first,json={"lines":[{"product_id":product["id"],"quantity":1}]}).json()
        assert client.patch(f"/api/v1/orders/{admin_order['id']}/approve",headers=admin,json={}).status_code==200

        rejected_order=client.post("/api/v1/client/orders",headers=second,json={"lines":[{"product_id":product["id"],"quantity":2}]}).json()
        before=next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product["id"])["stock"]
        assert client.patch(f"/api/v1/orders/{rejected_order['id']}/reject",headers=buyer,json={}).status_code==422
        refused=client.patch(f"/api/v1/orders/{rejected_order['id']}/reject",headers=buyer,json={"reason":"Demande incomplète"})
        assert refused.status_code==200 and refused.json()["status"]=="rejected"
        assert next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product["id"])["stock"]==before

        isolated=client.get("/api/v1/client/orders",headers=second).json()
        assert [x["id"] for x in isolated]==[rejected_order["id"]]
        all_orders=client.get("/api/v1/orders",headers=buyer)
        assert all_orders.status_code==200 and len(all_orders.json())>=3

        scarce=client.post("/api/v1/client/orders",headers=first,json={"lines":[{"product_id":product["id"],"quantity":5}]}).json()
        assert client.post("/api/v1/stock/movements",headers=admin,json={"product_id":product["id"],"movement_type":"INVENTAIRE","quantity":1,"reason":"Inventaire test"}).status_code==201
        insufficient=client.patch(f"/api/v1/orders/{scarce['id']}/approve",headers=buyer,json={})
        assert insufficient.status_code==409 and "Stock insuffisant" in insufficient.json()["detail"]
