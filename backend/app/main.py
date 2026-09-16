"""Point d'entrée FastAPI, cycle de vie et middlewares de sécurité."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.router import all_orders, approve_order, approve_user, deactivate_user, import_products, me, receive_purchase, register_client, reject_order, reject_user, router, staff_order
from app.chatbot.chatbot_router import router as chatbot_router
from app.agent.router import router as agent_router
from app.core.config import settings
from app.database.session import Base, SessionLocal, engine
from app.database.migrations import backfill_client_accounts, migrate_sqlite
from app.models.entities import Role, User
from app.security.auth import hash_password
from app.services.demo_suppliers import seed_demo_suppliers
from sqlalchemy import func, select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("soremed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    database_path = Path(engine.url.database or "").resolve() if engine.dialect.name == "sqlite" else engine.url.render_as_string(hide_password=True)
    logger.info("Base de données utilisée : %s", database_path)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).resolve().parent.mkdir(parents=True, exist_ok=True)
    migrate_sqlite(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower())):
            db.add(User(full_name="Administrateur SOREMED", email=settings.bootstrap_admin_email.lower(), password_hash=hash_password(settings.bootstrap_admin_password), role=Role.ADMIN))
            db.commit(); logger.warning("Compte administrateur initial créé; changez son mot de passe en production")
        linked_clients = backfill_client_accounts(db)
        if linked_clients: logger.info("%s compte(s) Client associés ou synchronisés", linked_clients)
        seeded_suppliers = seed_demo_suppliers(db)
        if seeded_suppliers: logger.info("%s fournisseur(s) de démonstration créé(s)", seeded_suppliers)
        unlinked_clients = db.scalar(select(func.count(User.id)).where(User.role == Role.CLIENT, User.client_id.is_(None))) or 0
        if unlinked_clients:
            logger.warning("%s compte(s) Client doivent être liés à une fiche client depuis Utilisateurs", unlinked_clients)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.include_router(router, prefix=settings.api_prefix)
app.include_router(chatbot_router, prefix=f"{settings.api_prefix}/chatbot", tags=["Assistant SOREMED"])
app.include_router(chatbot_router, prefix="/api/chatbot", tags=["Assistant SOREMED"])
app.include_router(agent_router, prefix=f"{settings.api_prefix}/agent", tags=["Agent métier SOREMED"])
# Alias ciblés demandés, sans casser les routes versionnées /api/v1 existantes.
app.add_api_route("/api/auth/register", register_client, methods=["POST"], status_code=201, tags=["Authentification"])
app.add_api_route("/api/auth/me", me, methods=["GET"], tags=["Authentification"])
app.add_api_route("/api/users/{user_id}/approve", approve_user, methods=["PATCH"], tags=["Utilisateurs"])
app.add_api_route("/api/users/{user_id}/reject", reject_user, methods=["PATCH"], tags=["Utilisateurs"])
app.add_api_route("/api/users/{user_id}/deactivate", deactivate_user, methods=["PATCH"], tags=["Utilisateurs"])
app.add_api_route("/api/products/import", import_products, methods=["POST"], tags=["Produits"])
app.add_api_route("/api/orders", all_orders, methods=["GET"], tags=["Commandes"])
app.add_api_route("/api/orders/{order_id}", staff_order, methods=["GET"], tags=["Commandes"])
app.add_api_route("/api/orders/{order_id}/approve", approve_order, methods=["PATCH"], tags=["Commandes"])
app.add_api_route("/api/orders/{order_id}/reject", reject_order, methods=["PATCH"], tags=["Commandes"])
app.add_api_route("/api/purchases/{purchase_id}/receive", receive_purchase, methods=["PATCH"], tags=["Achats"])


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, error: RequestValidationError):
    fields = [".".join(str(part) for part in item["loc"] if part != "body") for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": f"Données invalides : {', '.join(fields)}"})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, error: Exception):
    logger.exception("Erreur non gérée sur %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Une erreur interne est survenue"})


@app.get("/health", tags=["Système"])
def health():
    return {"status": "ok", "service": "plateforme-locale"}
