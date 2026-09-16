"""Flux public d'inscription et validation administrative."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app


def token(client: TestClient, email: str, password: str) -> dict[str,str]:
    response=client.post("/api/v1/auth/login",json={"email":email,"password":password})
    assert response.status_code==200,response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


def test_registration_pending_approval_and_activation():
    suffix=uuid4().hex[:8];email=f"inscription-{suffix}@example.com"
    payload={"full_name":"Nouveau Client","email":email,"phone":"0612345678","password":"Client123!","password_confirmation":"Client123!","company_name":"Nouvelle Société","ice":f"ICE-{suffix}","rc":"RC-10","address":"10 rue Test","city":"Casablanca","accepted_terms":True,"role":"admin"}
    with TestClient(app) as client:
        registered=client.post("/api/auth/register",json=payload)
        assert registered.status_code==201,registered.text
        assert "administrateur doit approuver" in registered.json()["message"]
        duplicate=client.post("/api/auth/register",json=payload)
        assert duplicate.status_code==409

        wrong=client.post("/api/v1/auth/login",json={"email":email,"password":"Erreur123!"})
        assert wrong.status_code==401 and wrong.json()["detail"]=="Email ou mot de passe incorrect"
        pending=client.post("/api/v1/auth/login",json={"email":email,"password":"Client123!"})
        assert pending.status_code==403 and "attente" in pending.json()["detail"]
        assert client.get("/api/v1/client/orders").status_code==401

        admin=token(client,"test-admin@example.com","test-only-password")
        users=client.get("/api/v1/users",headers=admin,params={"approval_status":"pending"}).json()
        account=next(x for x in users if x["email"]==email)
        assert account["role"]=="client" and account["is_active"] is False
        assert account["approval_status"]=="pending" and account["client_id"]
        record=next(x for x in client.get("/api/v1/clients",headers=admin).json() if x["id"]==account["client_id"])
        assert record["name"]==payload["full_name"] and record["email"]==email and record["status"]=="pending"
        assert record["phone"]==payload["phone"] and record["company_name"]==payload["company_name"]

        staff_email=f"staff-{suffix}@soremed.ma"
        staff=client.post("/api/v1/users",headers=admin,json={"full_name":"Agent Achats","email":staff_email,"password":"Staff123!","role":"achats"})
        assert staff.status_code==201,staff.text
        staff_token=token(client,staff_email,"Staff123!")
        assert client.patch(f"/api/v1/users/{account['id']}/approve",headers=staff_token).status_code==403

        approved=client.patch(f"/api/users/{account['id']}/approve",headers=admin)
        assert approved.status_code==200,approved.text
        assert approved.json()["is_active"] is True and approved.json()["approval_status"]=="approved"
        assert approved.json()["approved_at"] and approved.json()["approved_by"]
        active_record=next(x for x in client.get("/api/v1/clients",headers=admin).json() if x["id"]==account["client_id"])
        assert active_record["status"]=="active"

        client_token=token(client,email,"Client123!")
        me=client.get("/api/auth/me",headers=client_token)
        assert me.status_code==200
        assert {"id","full_name","email","role","is_active","client_id"}.issubset(me.json())
        assert client.get("/api/v1/client/orders",headers=client_token).status_code==200
