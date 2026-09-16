"""Permissions et réponses locales de l'Assistant SOREMED."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

def login(client,email,password):
    response=client.post("/api/v1/auth/login",json={"email":email,"password":password});assert response.status_code==200,response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}

def test_chatbot_local_role_permissions_and_private_orders():
    suffix=uuid4().hex[:7]
    with TestClient(app) as client:
        assert client.post("/api/v1/chatbot/message",json={"message":"Bonjour"}).status_code==401
        admin=login(client,"test-admin@example.com","test-only-password")
        buyer_email=f"bot-achats-{suffix}@example.com";client.post("/api/v1/users",headers=admin,json={"full_name":"Bot Achats","email":buyer_email,"password":"Achats123!","role":"achats"});buyer=login(client,buyer_email,"Achats123!")
        def customer(n):
            email=f"bot-client-{n}-{suffix}@example.com";created=client.post("/api/v1/users",headers=admin,json={"full_name":f"Bot Client {n}","email":email,"password":"Client123!","role":"client"});assert created.status_code==201;return login(client,email,"Client123!")
        first,second=customer(1),customer(2)
        product=client.post("/api/v1/products",headers=admin,json={"reference":f"BOT-{suffix}","name":"Produit chatbot","description":None,"price":25,"photo_path":None,"category_id":None,"stock":10,"minimum_stock":2,"barcode":None,"status":"active"}).json()
        assert client.post("/api/v1/stock/movements",headers=admin,json={"product_id":product["id"],"movement_type":"AJUSTEMENT_POSITIF","quantity":10,"reason":"Stock de test"}).status_code==201
        first_order=client.post("/api/v1/client/orders",headers=first,json={"lines":[{"product_id":product["id"],"quantity":1}]}).json();second_order=client.post("/api/v1/client/orders",headers=second,json={"lines":[{"product_id":product["id"],"quantity":1}]}).json()
        search=client.post("/api/v1/chatbot/message",headers=first,json={"message":f"Le produit {product['reference']} est-il disponible ?"});assert search.status_code==200 and search.json()["data"];assert "stock" not in search.json()["data"][0]
        own=client.post("/api/v1/chatbot/message",headers=first,json={"message":f"Où est ma commande {first_order['number']} ?"}).json();assert first_order["number"] in own["answer"]
        foreign=client.post("/api/v1/chatbot/message",headers=first,json={"message":f"Où est ma commande {second_order['number']} ?"}).json();assert foreign["data"]==[] and second_order["number"] not in foreign["answer"]
        pending=client.post("/api/v1/chatbot/message",headers=buyer,json={"message":"Montre les commandes en attente"}).json();assert pending["intent"]=="pending_customer_orders_list" and len(pending["data"])>=2
        denied=client.post("/api/v1/chatbot/message",headers=first,json={"message":f"Approuve {first_order['number']}"}).json();assert denied["intent"]=="forbidden"
        confirmation=client.post("/api/v1/chatbot/message",headers=buyer,json={"message":f"Approuve {first_order['number']}"}).json();assert confirmation["confirmation_required"] is True
        summary=client.post("/api/v1/chatbot/message",headers=admin,json={"message":"Donne le résumé du tableau de bord"}).json();assert summary["intent"]=="dashboard_summary" and summary["data"]
        assert client.post("/api/v1/chatbot/message",headers=admin,json={"message":"cmb util"}).json()["intent"]=="users_count"
        assert client.post("/api/v1/chatbot/message",headers=admin,json={"message":"nb prod"}).json()["intent"]=="products_count"
        assert client.post("/api/v1/chatbot/message",headers=buyer,json={"message":"cmb cmd en att"}).json()["intent"]=="pending_customer_orders_count"
        assert client.post("/api/v1/chatbot/message",headers=buyer,json={"message":"ach a rec"}).json()["intent"]=="pending_purchases_list"
        assert client.post("/api/v1/chatbot/message",headers=buyer,json={"message":"cmb util"}).json()["intent"]=="forbidden"
        assert client.post("/api/v1/chatbot/message",headers=buyer,json={"message":"stok bas"}).json()["intent"]=="low_stock_products"
        assert client.post("/api/v1/chatbot/message",headers=buyer,json={"message":"cmb en att"}).json()["intent"]=="clarification_required"
        assert client.post("/api/v1/chatbot/message",headers=first,json={"message":"mes cmd"}).json()["intent"]=="my_orders_list"
        assert client.post("/api/v1/chatbot/message",headers=first,json={"message":"stat der cmd"}).json()["intent"]=="my_last_order"
        assert client.post("/api/v1/chatbot/message",headers=first,json={"message":"ch7al men produit"}).json()["intent"]=="search_product"
        assert client.post("/api/v1/chatbot/message",headers=first,json={"message":"fin wslet cmd dyali"}).json()["intent"]=="my_last_order"
        assert client.post("/api/v1/chatbot/message",headers=first,json={"message":"bghit nchof ga3 users"}).json()["intent"]=="forbidden"
        unknown=client.post("/api/v1/chatbot/message",headers=admin,json={"message":"phrase sans rapport xyz"}).json();assert unknown["intent"]=="unknown" and unknown["suggested_actions"]
        history=client.get("/api/v1/chatbot/history",headers=first);assert history.status_code==200 and all("password" not in str(x).lower() and "token" not in str(x).lower() for x in history.json())
        assert client.delete("/api/v1/chatbot/history",headers=first).status_code==204


def test_chatbot_normalization_preserves_references():
    from app.chatbot.chatbot_abbreviations import normalize_message
    assert "MED-0008" in normalize_message("prix prod MED-0008").upper()
    assert normalize_message("cmb de cmd en attente ?")=="combien de commande en attente"
