"""Création automatique, synchronisation et isolation des comptes Client."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response=client.post("/api/v1/auth/login",json={"email":email,"password":password})
    assert response.status_code==200,response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


def test_client_accounts_catalog_orders_and_lifecycle():
    suffix=uuid4().hex[:8]
    with TestClient(app) as client:
        admin=login(client,"test-admin@example.com","test-only-password")
        initial_client_count=client.get("/api/v1/dashboard",headers=admin).json()["clients_count"]

        first_email=f"client-1-{suffix}@example.com"
        first_account=client.post("/api/v1/users",headers=admin,json={"full_name":"Client Initial","email":first_email,"password":"Client123!","role":"client"})
        assert first_account.status_code==201,first_account.text
        first_user_id=first_account.json()["id"];first_client_id=first_account.json()["client_id"]
        clients=client.get("/api/v1/clients",headers=admin).json()
        first_record=next(x for x in clients if x["id"]==first_client_id)
        assert first_record["name"]=="Client Initial" and first_record["email"]==first_email

        second_email=f"client-2-{suffix}@example.com"
        existing=client.post("/api/v1/clients",headers=admin,json={"name":"Fiche existante","company_name":"Entreprise 2","ice":f"ICE-{suffix}","rc":None,"address":None,"city":"Rabat","phone":None,"email":second_email,"status":"active"})
        assert existing.status_code==201,existing.text
        second_account=client.post("/api/v1/users",headers=admin,json={"full_name":"Client Deux","email":second_email,"password":"Client123!","role":"client"})
        assert second_account.status_code==201,second_account.text
        assert second_account.json()["client_id"]==existing.json()["id"]
        same_email=[x for x in client.get("/api/v1/clients",headers=admin).json() if x.get("email")==second_email]
        assert len(same_email)==1
        assert client.get("/api/v1/dashboard",headers=admin).json()["clients_count"]==initial_client_count+2

        synchronized_email=f"client-modifie-{suffix}@example.com"
        edited=client.put(f"/api/v1/users/{first_user_id}",headers=admin,json={"full_name":"Client Modifié","email":synchronized_email,"role":"client"})
        assert edited.status_code==200,edited.text
        synchronized=next(x for x in client.get("/api/v1/clients",headers=admin).json() if x["id"]==first_client_id)
        assert synchronized["name"]=="Client Modifié" and synchronized["email"]==synchronized_email

        product=client.post("/api/v1/products",headers=admin,json={"reference":f"CAT-{suffix}","name":"Produit catalogue","description":"Visible client","price":125.5,"photo_path":None,"category_id":None,"stock":10,"minimum_stock":1,"barcode":f"BC-{suffix}","status":"active"})
        assert product.status_code==201,product.text;product_id=product.json()["id"]
        assert client.post("/api/v1/stock/movements",headers=admin,json={"product_id":product_id,"movement_type":"AJUSTEMENT_POSITIF","quantity":10,"reason":"Stock de test"}).status_code==201

        first=login(client,synchronized_email,"Client123!")
        catalogue=client.get("/api/v1/products",headers=first)
        assert catalogue.status_code==200 and any(x["id"]==product_id for x in catalogue.json())
        for forbidden in ("dashboard","users","clients","suppliers","purchases","stock/movements","reports/stock.xlsx","audit","settings"):
            assert client.get(f"/api/v1/{forbidden}",headers=first).status_code==403,forbidden
        order1=client.post("/api/v1/client/orders",headers=first,json={"lines":[{"product_id":product_id,"quantity":2,"unit_price":0.01}]})
        assert order1.status_code==201,order1.text
        assert float(order1.json()["total"])==251 and float(order1.json()["lines"][0]["unit_price"])==125.5

        second=login(client,second_email,"Client123!")
        order2=client.post("/api/v1/client/orders",headers=second,json={"lines":[{"product_id":product_id,"quantity":1}]})
        assert order2.status_code==201,order2.text
        assert [x["id"] for x in client.get("/api/v1/client/orders",headers=second).json()]==[order2.json()["id"]]
        assert client.get(f"/api/v1/client/orders/{order1.json()['id']}",headers=second).status_code==404
        assert [x["id"] for x in client.get("/api/v1/client/orders",headers=first).json()]==[order1.json()["id"]]

        # Une commande conserve la fiche et transforme la suppression en désactivation.
        assert client.delete(f"/api/v1/users/{first_user_id}",headers=admin).status_code==204
        saved_user=next(x for x in client.get("/api/v1/users",headers=admin).json() if x["id"]==first_user_id)
        assert saved_user["is_active"] is False
        assert any(x["id"]==first_client_id for x in client.get("/api/v1/clients",headers=admin).json())
        assert client.post("/api/v1/auth/login",json={"email":synchronized_email,"password":"Client123!"}).status_code==403

        # Sans commande, compte et fiche automatiquement créée sont supprimés ensemble.
        third_email=f"client-3-{suffix}@example.com"
        third=client.post("/api/v1/users",headers=admin,json={"full_name":"Client Trois","email":third_email,"password":"Client123!","role":"client"}).json()
        assert client.delete(f"/api/v1/users/{third['id']}",headers=admin).status_code==204
        assert all(x["id"]!=third["client_id"] for x in client.get("/api/v1/clients",headers=admin).json())
