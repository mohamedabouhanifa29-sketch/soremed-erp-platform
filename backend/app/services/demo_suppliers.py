"""Amorçage idempotent des fournisseurs de démonstration SOREMED."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Supplier

DEMO_SUPPLIERS = (
    {"name":"Atlas Pharma Distribution","company_name":"Atlas Pharma Distribution SARL","ice":"DEMO-ICE-001","rc":"DEMO-RC-001","email":"contact@atlas-pharma.example.com","phone":"0600000001","address":"Zone industrielle Tassila","city":"Agadir","primary_contact":"Youssef Amrani","status":"active"},
    {"name":"Maroc Santé Médical","company_name":"Maroc Santé Médical SARL","ice":"DEMO-ICE-002","rc":"DEMO-RC-002","email":"commercial@maroc-sante.example.com","phone":"0600000002","address":"Sidi Ghanem","city":"Marrakech","primary_contact":"Salma Bennani","status":"active"},
    {"name":"PharmaLog Maroc","company_name":"PharmaLog Maroc SA","ice":"DEMO-ICE-003","rc":"DEMO-RC-003","email":"commandes@pharmalog.example.com","phone":"0600000003","address":"Parc industriel Bouskoura","city":"Casablanca","primary_contact":"Hamza El Idrissi","status":"active"},
    {"name":"BioCare Distribution","company_name":"BioCare Distribution SARL","ice":"DEMO-ICE-004","rc":"DEMO-RC-004","email":"contact@biocare.example.com","phone":"0600000004","address":"Avenue Mohammed VI","city":"Rabat","primary_contact":"Imane Alaoui","status":"active"},
    {"name":"Souss Medical Services","company_name":"Souss Medical Services SARL","ice":"DEMO-ICE-005","rc":"DEMO-RC-005","email":"commandes@souss-medical.example.com","phone":"0600000005","address":"Avenue Hassan II","city":"Agadir","primary_contact":"Mehdi Ait Ali","status":"active"},
)

def seed_demo_suppliers(db: Session) -> int:
    """Crée uniquement les fournisseurs dont l'ICE n'existe pas déjà."""
    expected=[item["ice"] for item in DEMO_SUPPLIERS]
    existing=set(db.scalars(select(Supplier.ice).where(Supplier.ice.in_(expected))))
    missing=[Supplier(**item) for item in DEMO_SUPPLIERS if item["ice"] not in existing]
    if missing:
        db.add_all(missing);db.commit()
    return len(missing)
