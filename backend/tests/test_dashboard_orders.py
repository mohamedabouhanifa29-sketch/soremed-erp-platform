"""Agrégats globaux des commandes clientes pour les dashboards Admin et Achats."""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.models.entities import Client, CustomerOrder, OrderStatus


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email":email,"password":password})
    assert response.status_code == 200, response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}


def test_dashboard_counts_all_order_workflow_statuses_for_admin_and_purchases():
    suffix=uuid4().hex[:8]
    with TestClient(app) as client:
        admin=login(client,"test-admin@example.com","test-only-password")
        before=client.get("/api/v1/dashboard",headers=admin).json()
        buyer_email=f"dashboard-achats-{suffix}@example.com"
        created=client.post("/api/v1/users",headers=admin,json={"full_name":"Achats Dashboard","email":buyer_email,"password":"Achats123!","role":"achats"})
        assert created.status_code==201,created.text
        buyer=login(client,buyer_email,"Achats123!")

        with SessionLocal() as db:
            customer=Client(name=f"Client Dashboard {suffix}",email=f"dashboard-client-{suffix}@example.com",status="active")
            db.add(customer);db.flush()
            specifications=[
                (OrderStatus.PENDING,Decimal("10.00"),None),
                (OrderStatus.APPROVED,Decimal("20.00"),datetime.now()),
                (OrderStatus.IN_PREPARATION,Decimal("30.00"),datetime.now()),
                (OrderStatus.SHIPPED,Decimal("40.00"),None),
                (OrderStatus.DELIVERED,Decimal("50.00"),None),
                (OrderStatus.REJECTED,Decimal("60.00"),None),
                (OrderStatus.CANCELLED,Decimal("70.00"),None),
            ]
            orders=[]
            for index,(status,total,approved_at) in enumerate(specifications):
                order=CustomerOrder(number=f"CMD-DASH-{suffix}-{index}",client_id=customer.id,status=status,total=total,approved_at=approved_at)
                db.add(order);orders.append(order)
            db.commit()
            process_ids={orders[0].id,orders[1].id,orders[2].id}

        summary=client.get("/api/v1/dashboard",headers=admin)
        assert summary.status_code==200,summary.text
        data=summary.json()
        assert data["pending_orders"]==before["pending_orders"]+1
        assert data["total_orders"]==before["total_orders"]+7
        assert data["approved_orders"]==before["approved_orders"]+1
        assert data["approved_today"]==before["approved_today"]+1
        assert data["in_preparation"]==before["in_preparation"]+1
        assert data["shipped_orders"]==before["shipped_orders"]+1
        assert data["rejected_orders"]==before["rejected_orders"]+1
        assert Decimal(str(data["approved_amount"]))==Decimal(str(before["approved_amount"]))+Decimal("140.00")
        returned={item["id"] for item in data["orders_to_process"]}
        assert process_ids <= returned
        assert all(item["status"] in {"pending","approved","in_preparation"} for item in data["orders_to_process"])

        buyer_data=client.get("/api/v1/dashboard",headers=buyer)
        assert buyer_data.status_code==200
        assert buyer_data.json()["pending_orders"]==data["pending_orders"]
        assert buyer_data.json()["approved_amount"]==data["approved_amount"]
        assert {item["id"] for item in buyer_data.json()["orders_to_process"]}==returned
