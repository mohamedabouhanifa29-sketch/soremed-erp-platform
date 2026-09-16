"""Import Excel de 300 produits, mise à jour, validation et permissions."""
from io import BytesIO
from uuid import uuid4
from openpyxl import Workbook
from fastapi.testclient import TestClient
from app.main import app

HEADERS=["reference","nom","description","categorie","prix","stock","seuil_minimum","code_barres","statut"]


def excel_bytes(rows:list[list]) -> bytes:
    workbook=Workbook();sheet=workbook.active;sheet.append(HEADERS)
    for row in rows: sheet.append(row)
    output=BytesIO();workbook.save(output);workbook.close();return output.getvalue()


def login(client:TestClient,email:str,password:str)->dict[str,str]:
    response=client.post("/api/v1/auth/login",json={"email":email,"password":password})
    assert response.status_code==200,response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


def test_import_300_products_update_errors_and_permissions():
    suffix=uuid4().hex[:6]
    rows=[[f"IMP-{suffix}-{i:03d}",f"Produit {i:03d}",f"Description {i}","Catégorie A" if i%2 else "Catégorie B",i+0.5,i,5,f"CODE-{suffix}-{i:03d}","actif" if i%3 else "inactif"] for i in range(1,301)]
    content=excel_bytes(rows)
    with TestClient(app) as client:
        admin=login(client,"test-admin@example.com","test-only-password")
        imported=client.post("/api/products/import",headers=admin,files={"file":("catalogue.xlsx",content,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert imported.status_code==200,imported.text
        assert imported.json()=={"created":300,"updated":0,"ignored":0,"errors":[]}
        products=client.get("/api/v1/products",headers=admin,params={"q":f"IMP-{suffix}"}).json()
        assert len(products)==300
        assert products[0]["reference"].startswith(f"IMP-{suffix}")

        update_rows=[rows[0].copy(),rows[1].copy(),[f"BAD-{suffix}","Produit invalide","","Catégorie A",-1,0,0,"","actif"]]
        update_rows[0][1]="Produit modifié A";update_rows[0][5]=99
        update_rows[1][1]="Produit modifié B";update_rows[1][8]="inactif"
        updated=client.post("/api/v1/products/import",headers=admin,files={"file":("mise-a-jour.xlsx",excel_bytes(update_rows),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert updated.status_code==200,updated.text
        assert updated.json()["created"]==0 and updated.json()["updated"]==2
        assert updated.json()["ignored"]==1 and updated.json()["errors"][0]["row"]==4

        client_email=f"import-client-{suffix}@example.com"
        account=client.post("/api/v1/users",headers=admin,json={"full_name":"Client Import","email":client_email,"password":"Client123!","role":"client"})
        assert account.status_code==201,account.text
        client_token=login(client,client_email,"Client123!")
        forbidden=client.post("/api/products/import",headers=client_token,files={"file":("catalogue.xlsx",content,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert forbidden.status_code==403
        wrong=client.post("/api/products/import",headers=admin,files={"file":("catalogue.xls",content,"application/vnd.ms-excel")})
        assert wrong.status_code==400
        audit=client.get("/api/v1/audit",headers=admin,params={"q":"import Excel"}).json()
        assert audit and "Importés: 300" in audit[-1 if len(audit)>1 else 0]["details"]
        assert audit[0]["ip_address"]
