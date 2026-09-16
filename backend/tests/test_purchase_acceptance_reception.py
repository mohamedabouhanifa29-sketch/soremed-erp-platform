"""Workflow fournisseur : acceptation sans stock puis réceptions cumulatives."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app


def login(client:TestClient,email:str,password:str)->dict[str,str]:
    response=client.post("/api/v1/auth/login",json={"email":email,"password":password})
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


def test_supplier_acceptance_and_partial_receptions():
    suffix=uuid4().hex[:7]
    with TestClient(app) as client:
        admin=login(client,"test-admin@example.com","test-only-password")
        product=client.post("/api/v1/products",headers=admin,json={"reference":f"REC-{suffix}","name":"Produit réception","description":None,"price":10,"photo_path":None,"category_id":None,"stock":0,"minimum_stock":0,"barcode":None,"status":"active"}).json()
        supplier=client.post("/api/v1/suppliers",headers=admin,json={"name":"Fournisseur réception","company_name":None,"ice":f"REC-{suffix}","rc":None,"email":None,"phone":None,"address":None,"city":None,"primary_contact":None,"status":"active"}).json()
        purchase=client.post("/api/v1/purchases",headers=admin,json={"number":f"REC-{suffix}","supplier_id":supplier["id"],"status":"COMMANDE_ENVOYEE","notes":None,"lines":[{"product_id":product["id"],"quantity":5,"unit_price":8,"discount":0,"tax_rate":0}]}).json()
        accepted=client.patch(f"/api/v1/purchases/{purchase['id']}/supplier-accepted",headers=admin,json={"comment":"Acceptée par téléphone","reference":"CONF-1"})
        assert accepted.status_code==200 and accepted.json()["status"]=="CONFIRMEE_PAR_FOURNISSEUR"
        assert next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product["id"])["stock"]==0
        partial=client.post(f"/api/v1/purchases/{purchase['id']}/receive",headers=admin,json={"items":[{"product_id":product["id"],"received_quantity":2,"comment":"Premier colis"}],"comment":"Réception partielle"})
        assert partial.status_code==200 and partial.json()["status"]=="RECEPTIONNEE" and partial.json()["lines"][0]["received_quantity"]==2
        assert next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product["id"])["stock"]==2
        assert client.post(f"/api/v1/purchases/{purchase['id']}/receive",headers=admin,json={"items":[{"product_id":product["id"],"received_quantity":1}]}).status_code==409
