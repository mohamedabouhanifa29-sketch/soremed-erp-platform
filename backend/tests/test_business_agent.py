"""Sécurité, confirmation et absence d'effet de bord de l'agent métier."""
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from app.database.session import SessionLocal
from app.main import app
from app.models.entities import Product,Purchase,Supplier,SupplierProduct
from app.agent.confirmations import PendingConfirmation,_pending,consume,create
from datetime import datetime,timedelta,timezone

def login(client,email,password):
 response=client.post("/api/v1/auth/login",json={"email":email,"password":password});assert response.status_code==200,response.text
 return {"Authorization":f"Bearer {response.json()['access_token']}"}

def test_agent_reads_enforces_roles_and_confirms_draft_once():
 suffix=uuid4().hex[:7]
 with TestClient(app) as client:
  admin=login(client,"test-admin@example.com","test-only-password")
  answer=client.post("/api/v1/agent/message",headers=admin,json={"message":"cmb prod"})
  assert answer.status_code==200 and answer.json()["type"]=="answer"
  with SessionLocal() as db:
   supplier=Supplier(name=f"Agent fournisseur {suffix}",ice=f"AG-{suffix}",status="active");product=Product(reference=f"AG-{suffix}",name="Cardio Agent",price=20,stock=0,minimum_stock=5,status="active")
   db.add_all([supplier,product]);db.flush();db.add(SupplierProduct(supplier_id=supplier.id,product_id=product.id,purchase_price=Decimal("8"),is_active=True));db.commit();product_id=product.id
  before=len(client.get("/api/v1/purchases",headers=admin).json())
  proposal=client.post("/api/v1/agent/message",headers=admin,json={"message":"Prépare un brouillon d'achat pour les produits sous le stock minimum"})
  assert proposal.status_code==200 and proposal.json()["type"]=="confirmation_required"
  assert len(client.get("/api/v1/purchases",headers=admin).json())==before
  token=proposal.json()["confirmation_token"]
  confirmed=client.post("/api/v1/agent/confirm",headers=admin,json={"confirmation_token":token})
  assert confirmed.status_code==200 and confirmed.json()["data"]["status"]=="EN_PREPARATION"
  assert len(client.get("/api/v1/purchases",headers=admin).json())==before+1
  product=next(x for x in client.get("/api/v1/products",headers=admin).json() if x["id"]==product_id);assert product["stock"]==0
  assert client.post("/api/v1/agent/confirm",headers=admin,json={"confirmation_token":token}).status_code==409

def test_client_cannot_read_supplier_purchases_through_agent():
 suffix=uuid4().hex[:7]
 with TestClient(app) as client:
  admin=login(client,"test-admin@example.com","test-only-password");email=f"agent-client-{suffix}@example.com"
  created=client.post("/api/v1/users",headers=admin,json={"full_name":"Client Agent","email":email,"password":"Client123!","role":"client"});assert created.status_code==201
  customer=login(client,email,"Client123!")
  forbidden=client.post("/api/v1/agent/message",headers=customer,json={"message":"quels achats sont à réceptionner ?"})
  assert forbidden.status_code==200 and forbidden.json()["type"]=="error" and "rôle" in forbidden.json()["message"]

def test_confirmation_is_bound_to_owner_and_expires():
 token=create(10,"admin","CREATE_PURCHASE_DRAFT",{})
 try:consume(token,11,"admin");assert False,"un autre utilisateur ne doit pas consommer le jeton"
 except PermissionError:pass
 assert consume(token,10,"admin").user_id==10
 expired=create(10,"admin","CREATE_PURCHASE_DRAFT",{})
 _pending[expired].expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
 try:consume(expired,10,"admin");assert False,"un jeton expiré doit être refusé"
 except ValueError as error:assert "expiré" in str(error)
