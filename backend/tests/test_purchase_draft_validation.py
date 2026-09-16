"""Validation des brouillons et calculs serveur des achats fournisseurs."""
from uuid import uuid4
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import SessionLocal
from app.models.entities import Purchase, PurchaseLine

def test_purchase_draft_confirmation_and_financial_calculation():
    suffix=uuid4().hex[:7]
    with TestClient(app) as client:
        login=client.post("/api/v1/auth/login",json={"email":"test-admin@example.com","password":"test-only-password"});headers={"Authorization":f"Bearer {login.json()['access_token']}"}
        draft=client.post("/api/v1/purchases",headers=headers,json={"number":f"BR-{suffix}","supplier_id":None,"status":"draft","purchase_date":"2026-07-28T00:00:00","expected_delivery_date":None,"notes":"Brouillon incomplet","lines":[]})
        assert draft.status_code==201,draft.text
        assert float(draft.json()["total"])==0 and draft.json()["status"]=="EN_PREPARATION"
        assert client.patch(f"/api/v1/purchases/{draft.json()['id']}/receive",headers=headers).status_code==409
        product=client.post("/api/v1/products",headers=headers,json={"reference":f"CAL-{suffix}","name":"Produit calcul","description":None,"price":1,"default_purchase_price":75,"photo_path":None,"category_id":None,"stock":5,"minimum_stock":1,"barcode":None,"status":"active"}).json()
        supplier=client.post("/api/v1/suppliers",headers=headers,json={"name":"Fournisseur calcul","company_name":None,"ice":f"CAL-{suffix}","rc":None,"email":None,"phone":None,"address":None,"city":None,"primary_contact":None,"status":"active"}).json()
        base={"number":f"CF-{suffix}","status":"ordered","purchase_date":"2026-07-28T00:00:00","expected_delivery_date":None,"notes":None,"lines":[{"product_id":product["id"],"quantity":2,"unit_price":100,"discount":10,"tax_rate":20}]}
        assert client.post("/api/v1/purchases",headers=headers,json={**base,"supplier_id":None}).status_code==422
        assert client.post("/api/v1/purchases",headers=headers,json={**base,"supplier_id":supplier["id"],"lines":[]}).status_code==422
        duplicate={**base,"supplier_id":supplier["id"],"lines":base["lines"]*2};assert client.post("/api/v1/purchases",headers=headers,json=duplicate).status_code==422
        automatic=client.get(f"/api/v1/products/{product['id']}/purchase-price",headers=headers,params={"supplier_id":supplier["id"]})
        assert automatic.status_code==200 and float(automatic.json()["purchase_price"])==75 and automatic.json()["source"]=="product_default"
        confirmed=client.post("/api/v1/purchases",headers=headers,json={**base,"supplier_id":supplier["id"],"subtotal":1,"tax_amount":1,"total":1})
        assert confirmed.status_code==201,confirmed.text
        body=confirmed.json();assert float(body["subtotal"])==180 and float(body["tax_amount"])==36 and float(body["total"])==216
        assert float(body["lines"][0]["tax_amount"])==36 and float(body["lines"][0]["total_amount"])==216
        assert body["supplier_confirmed_delivery_date"] is None
        purchase_id=body["id"]
        assert client.patch(f"/api/v1/purchases/{purchase_id}/receive",headers=headers).status_code==409
        assert client.patch(f"/api/v1/purchases/{purchase_id}/supplier-confirmation",headers=headers,json={"confirmation_reference":"CONF-1"}).status_code==422
        supplier_confirmation=client.patch(f"/api/v1/purchases/{purchase_id}/supplier-confirmation",headers=headers,json={"confirmed_delivery_date":"2026-08-05T00:00:00","confirmation_reference":"CONF-1","contact_name":"Contact test","comment":"Confirmé par téléphone"})
        assert supplier_confirmation.status_code==200,supplier_confirmation.text
        assert supplier_confirmation.json()["status"]=="CONFIRMEE_PAR_FOURNISSEUR" and supplier_confirmation.json()["supplier_confirmed_delivery_date"]
        reception=client.patch(f"/api/v1/purchases/{purchase_id}/receive",headers=headers)
        assert reception.status_code==200 and reception.json()["actual_reception_date"]
        supplier_tariff=client.get(f"/api/v1/products/{product['id']}/purchase-price",headers=headers,params={"supplier_id":supplier["id"]}).json()
        assert float(supplier_tariff["purchase_price"])==100 and supplier_tariff["source"]=="supplier_product"
        other=client.post("/api/v1/suppliers",headers=headers,json={"name":"Autre fournisseur","company_name":None,"ice":f"ALT-{suffix}","rc":None,"email":None,"phone":None,"address":None,"city":None,"primary_contact":None,"status":"active"}).json()
        with SessionLocal() as db:
            old=Purchase(number=f"HIST-{suffix}",supplier_id=other["id"],status="awaiting_receipt",subtotal=Decimal("60"),tax_amount=Decimal("0"),total=Decimal("60"))
            old.lines.append(PurchaseLine(product_id=product["id"],quantity=1,unit_price=Decimal("60"),discount=Decimal("0"),tax_rate=Decimal("0"),line_total=Decimal("60"),tax_amount=Decimal("0"),total_amount=Decimal("60")))
            db.add(old);db.commit()
        historical=client.get(f"/api/v1/products/{product['id']}/purchase-price",headers=headers,params={"supplier_id":other["id"]}).json()
        assert float(historical["purchase_price"])==60 and historical["source"]=="last_purchase"
        current=next(x for x in client.get("/api/v1/products",headers=headers).json() if x["id"]==product["id"]);assert current["stock"]==2
        assert client.patch(f"/api/v1/purchases/{purchase_id}/receive",headers=headers).status_code==409
