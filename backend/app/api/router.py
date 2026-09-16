"""API métier complète de la plateforme SOREMED."""
from __future__ import annotations
import shutil
import sqlite3
import logging
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.core.config import settings
from app.core.purchase_status import PURCHASE_STATUSES, PurchaseStatus
from app.database.session import engine, get_db
from app.models.entities import ApprovalStatus, AuditLog, Category, Client, CompanySetting, CustomerOrder, CustomerOrderLine, Favorite, MovementType, OrderStatus, Product, Purchase, PurchaseLine, Role, StockMovement, StockMovementType, Supplier, SupplierProduct, User
from app.schemas.domain import AuditRead, CategoryInput, CategoryRead, ClientInput, ClientRead, ClientRegister, CompanyInput, CompanyRead, CustomerOrderInput, CustomerOrderRead, DashboardRead, LoginRequest, MovementInput, MovementRead, OrderApprovalInput, OrderRejectionInput, PasswordChange, ProductInput, ProductRead, PurchaseInput, PurchasePriceRead, PurchaseRead, PurchaseReceptionInput, SupplierAcceptanceInput, SupplierConfirmationInput, SupplierInput, SupplierRead, TokenResponse, UserCreate, UserRead, UserUpdate
from app.security.auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from app.services.audit import record_action
from app.services.product_import import import_products_xlsx

router = APIRouter()
logger = logging.getLogger("soremed.dashboard")
ADMIN = require_roles(Role.ADMIN)
PURCHASE_STAFF = require_roles(Role.ADMIN, Role.PURCHASES)
CLIENT_STAFF = require_roles(Role.ADMIN)
ALL_ROLES = require_roles(Role.ADMIN, Role.PURCHASES, Role.CLIENT)
CLIENT_ONLY = require_roles(Role.CLIENT)


def fail_not_found(label: str) -> None:
    raise HTTPException(404, f"{label} introuvable")


def commit_or_conflict(db: Session, message: str = "Une valeur unique existe déjà") -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, message)


def flush_or_conflict(db: Session, message: str) -> None:
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, message)


def ensure_client_record(db: Session, full_name: str, email: str, preferred_id: int | None = None) -> Client:
    """Réutilise une fiche par identifiant ou email, sinon la crée automatiquement."""
    normalized_email = email.lower()
    client = db.get(Client, preferred_id) if preferred_id else None
    if not client:
        client = db.scalar(select(Client).where(func.lower(Client.email) == normalized_email).order_by(Client.id))
    if not client:
        client = Client(name=full_name.strip(), email=normalized_email, status="active")
        db.add(client)
        flush_or_conflict(db, "Impossible de créer la fiche client associée")
    else:
        client.name = full_name.strip()
        client.email = normalized_email
    return client


def sqlite_path() -> Path:
    if not settings.database_url.startswith("sqlite:///"):
        raise HTTPException(400, "Cette opération nécessite SQLite")
    value = settings.database_url.removeprefix("sqlite:///")
    return Path(value).resolve()


@router.post("/auth/login", response_model=TokenResponse, tags=["Authentification"])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    if user.approval_status == ApprovalStatus.PENDING:
        raise HTTPException(403, "Votre compte est en attente d’approbation par un administrateur.")
    if user.approval_status == ApprovalStatus.REJECTED:
        raise HTTPException(403, "Votre demande de création de compte a été refusée.")
    if not user.is_active:
        raise HTTPException(403, "Votre compte a été désactivé. Contactez un administrateur.")
    record_action(db, user, "connexion", "session", ip=request.client.host if request.client else None)
    db.commit()
    return TokenResponse(access_token=create_access_token(user))


@router.post("/auth/register", status_code=201, tags=["Authentification"])
def register_client(payload: ClientRegister, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Un compte existe déjà avec cette adresse email")
    client = db.scalar(select(Client).where(func.lower(Client.email) == email).order_by(Client.id))
    if not client:
        client = Client(name=payload.full_name.strip(), email=email)
        db.add(client)
    client.name = payload.full_name.strip(); client.email = email; client.phone = payload.phone.strip(); client.company_name = payload.company_name or None; client.ice = payload.ice or None; client.rc = payload.rc or None; client.address = payload.address or None; client.city = payload.city or None; client.status = "pending"
    user = User(full_name=payload.full_name.strip(), email=email, password_hash=hash_password(payload.password), role=Role.CLIENT, is_active=False, approval_status=ApprovalStatus.PENDING, client=client)
    db.add(user); flush_or_conflict(db, "Un compte existe déjà avec cette adresse email"); db.commit()
    return {"message": "Votre demande de création de compte a été enregistrée. Un administrateur doit approuver votre compte avant votre première connexion."}


@router.get("/auth/me", response_model=UserRead, tags=["Authentification"])
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/auth/password", tags=["Authentification"])
def change_password(payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Le mot de passe actuel est incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(400, "Le nouveau mot de passe doit être différent")
    user.password_hash = hash_password(payload.new_password); record_action(db, user, "mot de passe", "utilisateur", user.id); db.commit()
    return {"message": "Mot de passe modifié avec succès"}


@router.get("/users", response_model=list[UserRead], tags=["Utilisateurs"])
def users(q: str = "", role: Role | None = None, active: bool | None = None, approval_status: ApprovalStatus | None = None, db: Session = Depends(get_db), _: User = Depends(ADMIN)):
    stmt = select(User).order_by(User.full_name)
    if q: stmt = stmt.where(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    if role: stmt = stmt.where(User.role == role)
    if active is not None: stmt = stmt.where(User.is_active == active)
    if approval_status: stmt = stmt.where(User.approval_status == approval_status)
    return list(db.scalars(stmt.limit(500)))


@router.post("/users", response_model=UserRead, status_code=201, tags=["Utilisateurs"])
def add_user(payload: UserCreate, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    user = User(full_name=payload.full_name.strip(), email=payload.email.lower(), password_hash=hash_password(payload.password), role=payload.role)
    if payload.role == Role.CLIENT:
        user.client = ensure_client_record(db, user.full_name, user.email, payload.client_id)
        user.client.status = "active"
    user.approval_status = ApprovalStatus.APPROVED; user.approved_at = datetime.now().astimezone(); user.approved_by = actor.id
    db.add(user); flush_or_conflict(db, "Cette adresse email est déjà utilisée"); record_action(db, actor, "création", "utilisateur", user.id)
    commit_or_conflict(db, "Cette adresse email est déjà utilisée"); db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserRead, tags=["Utilisateurs"])
def edit_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    user = db.get(User, user_id)
    if not user: fail_not_found("Utilisateur")
    values = payload.model_dump(exclude_unset=True)
    password = values.pop("password", None)
    if password: user.password_hash = hash_password(password)
    if values.get("email"): values["email"] = values["email"].lower()
    resulting_role = values.get("role", user.role)
    resulting_name = values.get("full_name", user.full_name)
    resulting_email = values.get("email", user.email)
    preferred_client_id = values.pop("client_id", None) or user.client_id
    if resulting_role == Role.CLIENT:
        user.client = ensure_client_record(db, resulting_name, resulting_email, preferred_client_id)
    else:
        user.client = None
    for key, value in values.items(): setattr(user, key, value)
    record_action(db, actor, "modification", "utilisateur", user.id)
    commit_or_conflict(db); db.refresh(user)
    return user


@router.patch("/users/{user_id}/status", response_model=UserRead, tags=["Utilisateurs"])
def toggle_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    if actor.id == user_id: raise HTTPException(400, "Vous ne pouvez pas désactiver votre propre compte")
    user = db.get(User, user_id)
    if not user: fail_not_found("Utilisateur")
    user.is_active = not user.is_active; record_action(db, actor, "activation" if user.is_active else "désactivation", "utilisateur", user.id); db.commit(); db.refresh(user)
    return user


@router.patch("/users/{user_id}/approve", response_model=UserRead, tags=["Utilisateurs"])
def approve_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    user = db.get(User, user_id)
    if not user: fail_not_found("Utilisateur")
    if user.role == Role.CLIENT:
        user.client = ensure_client_record(db, user.full_name, user.email, user.client_id)
        user.client.status = "active"
    user.approval_status = ApprovalStatus.APPROVED; user.is_active = True; user.approved_at = datetime.now().astimezone(); user.approved_by = actor.id
    record_action(db, actor, "approbation", "utilisateur", user.id); db.commit(); db.refresh(user); return user


@router.patch("/users/{user_id}/reject", response_model=UserRead, tags=["Utilisateurs"])
def reject_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    if actor.id == user_id: raise HTTPException(400, "Vous ne pouvez pas refuser votre propre compte")
    user = db.get(User, user_id)
    if not user: fail_not_found("Utilisateur")
    user.approval_status = ApprovalStatus.REJECTED; user.is_active = False; user.approved_at = None; user.approved_by = actor.id
    if user.client: user.client.status = "rejected"
    record_action(db, actor, "refus", "utilisateur", user.id); db.commit(); db.refresh(user); return user


@router.patch("/users/{user_id}/deactivate", response_model=UserRead, tags=["Utilisateurs"])
def deactivate_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    if actor.id == user_id: raise HTTPException(400, "Vous ne pouvez pas désactiver votre propre compte")
    user = db.get(User, user_id)
    if not user: fail_not_found("Utilisateur")
    user.is_active = False
    if user.client: user.client.status = "inactive"
    record_action(db, actor, "désactivation", "utilisateur", user.id); db.commit(); db.refresh(user); return user


@router.delete("/users/{user_id}", status_code=204, tags=["Utilisateurs"])
def remove_user(user_id: int, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    if actor.id == user_id: raise HTTPException(400, "Vous ne pouvez pas supprimer votre propre compte")
    user = db.get(User, user_id)
    if not user: fail_not_found("Utilisateur")
    linked_client = user.client if user.role == Role.CLIENT else None
    if linked_client and db.scalar(select(func.count(CustomerOrder.id)).where(CustomerOrder.client_id == linked_client.id)):
        user.is_active = False
        record_action(db, actor, "désactivation", "utilisateur", user_id, "Compte conservé car des commandes lui sont associées")
        db.commit()
        return
    if linked_client:
        user.client = None
        db.flush()
        db.delete(linked_client)
    db.delete(user); record_action(db, actor, "suppression", "utilisateur", user_id); db.commit()


@router.get("/clients", response_model=list[ClientRead], tags=["Clients"])
def clients(q: str = "", status: str | None = None, city: str | None = None, db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    stmt = select(Client).order_by(Client.name)
    if q: stmt = stmt.where(or_(Client.name.ilike(f"%{q}%"), Client.company_name.ilike(f"%{q}%"), Client.ice.ilike(f"%{q}%"), Client.email.ilike(f"%{q}%")))
    if status: stmt = stmt.where(Client.status == status)
    if city: stmt = stmt.where(Client.city == city)
    return list(db.scalars(stmt.limit(500)))


@router.post("/clients", response_model=ClientRead, status_code=201, tags=["Clients"])
def add_client(payload: ClientInput, db: Session = Depends(get_db), actor: User = Depends(CLIENT_STAFF)):
    client = Client(**payload.model_dump()); db.add(client); flush_or_conflict(db, "Cet ICE est déjà utilisé"); record_action(db, actor, "création", "client", client.id); commit_or_conflict(db, "Cet ICE est déjà utilisé"); db.refresh(client); return client


@router.put("/clients/{client_id}", response_model=ClientRead, tags=["Clients"])
def edit_client(client_id: int, payload: ClientInput, db: Session = Depends(get_db), actor: User = Depends(CLIENT_STAFF)):
    client = db.get(Client, client_id)
    if not client: fail_not_found("Client")
    for key, value in payload.model_dump().items(): setattr(client, key, value)
    record_action(db, actor, "modification", "client", client.id); commit_or_conflict(db, "Cet ICE est déjà utilisé"); db.refresh(client); return client


@router.patch("/clients/{client_id}/status", response_model=ClientRead, tags=["Clients"])
def toggle_client(client_id: int, db: Session = Depends(get_db), actor: User = Depends(CLIENT_STAFF)):
    client = db.get(Client, client_id)
    if not client: fail_not_found("Client")
    client.status = "inactive" if client.status == "active" else "active"; record_action(db, actor, "changement statut", "client", client.id); db.commit(); db.refresh(client); return client


@router.delete("/clients/{client_id}", status_code=204, tags=["Clients"])
def remove_client(client_id: int, db: Session = Depends(get_db), actor: User = Depends(CLIENT_STAFF)):
    client = db.get(Client, client_id)
    if not client: fail_not_found("Client")
    db.delete(client); record_action(db, actor, "suppression", "client", client_id); db.commit()


@router.get("/categories", response_model=list[CategoryRead], tags=["Produits"])
def categories(db: Session = Depends(get_db), _: User = Depends(ALL_ROLES)):
    return list(db.scalars(select(Category).order_by(Category.name)))


@router.post("/categories", response_model=CategoryRead, status_code=201, tags=["Produits"])
def add_category(payload: CategoryInput, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    item = Category(name=payload.name.strip()); db.add(item); flush_or_conflict(db, "Cette catégorie existe déjà"); record_action(db, actor, "création", "catégorie", item.id); commit_or_conflict(db, "Cette catégorie existe déjà"); db.refresh(item); return item


@router.get("/products", response_model=list[ProductRead], tags=["Produits"])
def products(q: str = "", status: str | None = None, category_id: int | None = None, low_stock: bool = False, db: Session = Depends(get_db), user: User = Depends(ALL_ROLES)):
    stmt = select(Product).order_by(Product.name)
    if q:
        term=f"%{q.strip()}%";stmt=stmt.outerjoin(Product.category).where(or_(Product.name.ilike(term),Product.commercial_name.ilike(term),Product.active_ingredient.ilike(term),Product.reference.ilike(term),Product.barcode.ilike(term),Product.laboratory.ilike(term),Product.dosage.ilike(term),Category.name.ilike(term)))
    if status: stmt = stmt.where(Product.status == status)
    if category_id: stmt = stmt.where(Product.category_id == category_id)
    if low_stock: stmt = stmt.where(Product.stock <= Product.minimum_stock)
    if user.role == Role.CLIENT: stmt = stmt.where(Product.status == "active")
    return list(db.scalars(stmt.limit(500)))


@router.get("/products/{product_id}/purchase-price", response_model=PurchasePriceRead, tags=["Achats"])
def product_purchase_price(product_id: int, supplier_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    """Résout un tarif d'achat sans jamais remplacer le prix de vente du catalogue."""
    product = db.get(Product, product_id)
    if not product: fail_not_found("Produit")
    if supplier_id:
        supplier_price = db.scalar(select(SupplierProduct).where(SupplierProduct.supplier_id == supplier_id, SupplierProduct.product_id == product_id, SupplierProduct.is_active.is_(True)))
        if supplier_price:
            return PurchasePriceRead(product_id=product_id, supplier_id=supplier_id, purchase_price=supplier_price.purchase_price, source="supplier_product")
        last_price = db.scalar(select(PurchaseLine.unit_price).join(Purchase, Purchase.id == PurchaseLine.purchase_id).where(PurchaseLine.product_id == product_id, Purchase.supplier_id == supplier_id, Purchase.status.not_in((PurchaseStatus.PREPARATION,PurchaseStatus.CANCELLED))).order_by(Purchase.purchase_date.desc(), Purchase.id.desc()).limit(1))
        if last_price is not None:
            return PurchasePriceRead(product_id=product_id, supplier_id=supplier_id, purchase_price=last_price, source="last_purchase")
    if product.default_purchase_price is not None:
        return PurchasePriceRead(product_id=product_id, supplier_id=supplier_id, purchase_price=product.default_purchase_price, source="product_default")
    if product.price is not None and product.price > 0:
        return PurchasePriceRead(product_id=product_id, supplier_id=supplier_id, purchase_price=product.price, source="product_existing_price")
    return PurchasePriceRead(product_id=product_id, supplier_id=supplier_id, purchase_price=None, source="unavailable")


@router.get("/client/products/{product_id}", response_model=ProductRead, tags=["Espace client"])
def client_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(CLIENT_ONLY)):
    product = db.scalar(select(Product).where(Product.id == product_id, Product.status == "active"))
    if not product: fail_not_found("Produit")
    return product


@router.get("/favorites", response_model=list[ProductRead], tags=["Espace client"])
def favorites(db: Session = Depends(get_db), user: User = Depends(CLIENT_ONLY)):
    return list(db.scalars(select(Product).join(Favorite, Favorite.product_id == Product.id).where(Favorite.user_id == user.id, Product.status == "active").order_by(Favorite.created_at.desc())))


@router.post("/favorites/{product_id}", response_model=ProductRead, status_code=201, tags=["Espace client"])
def add_favorite(product_id: int, db: Session = Depends(get_db), user: User = Depends(CLIENT_ONLY)):
    product = db.scalar(select(Product).where(Product.id == product_id, Product.status == "active"))
    if not product: fail_not_found("Produit")
    if not db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.product_id == product_id)):
        db.add(Favorite(user_id=user.id, product_id=product_id)); db.commit()
    return product


@router.delete("/favorites/{product_id}", status_code=204, tags=["Espace client"])
def remove_favorite(product_id: int, db: Session = Depends(get_db), user: User = Depends(CLIENT_ONLY)):
    favorite = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.product_id == product_id))
    if favorite: db.delete(favorite); db.commit()


@router.post("/products", response_model=ProductRead, status_code=201, tags=["Produits"])
def add_product(payload: ProductInput, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    values = payload.model_dump(); values["stock"] = 0
    product = Product(**values); db.add(product); flush_or_conflict(db, "La référence ou le code-barres existe déjà"); record_action(db, actor, "création", "produit", product.id); commit_or_conflict(db, "La référence ou le code-barres existe déjà"); db.refresh(product); return product


@router.post("/products/import", tags=["Produits"])
async def import_products(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Seuls les fichiers Excel .xlsx sont acceptés")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Le fichier dépasse la taille maximale de 10 Mo")
    try:
        result = import_products_xlsx(content, db)
        db.flush()
        imported = result["created"] + result["updated"]
        record_action(db, actor, "import Excel", "produits", details=f"Importés: {imported}; créés: {result['created']}; mis à jour: {result['updated']}; ignorés: {result['ignored']}", ip=request.client.host if request.client else None)
        db.commit()
        return result
    except ValueError as error:
        db.rollback(); raise HTTPException(422, str(error))
    except Exception:
        db.rollback(); raise HTTPException(400, "Le fichier Excel est invalide ou corrompu")


@router.get("/products/import-template", tags=["Produits"])
def product_import_template(_: User = Depends(PURCHASE_STAFF)):
    """Retourne un modèle Excel local compatible avec l'import enrichi."""
    columns=["reference","commercial_name","active_ingredient","description","category","selling_price","stock","minimum_stock","barcode","status","laboratory","dosage","pharmaceutical_form","packaging","image_url"]
    book=Workbook();sheet=book.active;sheet.title="Produits";sheet.append(columns);sheet.append(["MED-0001","Cardiol 5 mg","Amlodipine","Produit de démonstration","Cardiologie",35.80,0,10,"6110000000001","active","Non renseigné","5 mg","Comprimé","Boîte de 30 comprimés",""])
    output=BytesIO();book.save(output);output.seek(0)
    return StreamingResponse(output,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=modele-import-produits.xlsx"})


@router.put("/products/{product_id}", response_model=ProductRead, tags=["Produits"])
def edit_product(product_id: int, payload: ProductInput, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    product = db.get(Product, product_id)
    if not product: fail_not_found("Produit")
    values = payload.model_dump()
    values.pop("stock", None)
    for key, value in values.items(): setattr(product, key, value)
    record_action(db, actor, "modification", "produit", product.id); commit_or_conflict(db, "La référence ou le code-barres existe déjà"); db.refresh(product); return product


@router.post("/products/{product_id}/photo", response_model=ProductRead, tags=["Produits"])
def product_photo(product_id: int, photo: UploadFile = File(...), db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    product = db.get(Product, product_id)
    if not product: fail_not_found("Produit")
    if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}: raise HTTPException(400, "Format accepté : JPG, PNG ou WebP")
    suffix = {"image/jpeg":".jpg", "image/png":".png", "image/webp":".webp"}[photo.content_type]
    folder = Path(settings.upload_dir).resolve() / "products"; folder.mkdir(parents=True, exist_ok=True)
    name = f"{product.id}-{uuid4().hex}{suffix}"; target = folder / name
    with target.open("wb") as output: shutil.copyfileobj(photo.file, output)
    product.photo_path = f"/uploads/products/{name}"; record_action(db, actor, "photo", "produit", product.id); db.commit(); db.refresh(product); return product


@router.patch("/products/{product_id}/status", response_model=ProductRead, tags=["Produits"])
def toggle_product(product_id: int, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    product = db.get(Product, product_id)
    if not product: fail_not_found("Produit")
    product.status = "inactive" if product.status == "active" else "active"; record_action(db, actor, "changement statut", "produit", product.id); db.commit(); db.refresh(product); return product


@router.delete("/products/{product_id}", status_code=204, tags=["Produits"])
def remove_product(product_id: int, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    product = db.get(Product, product_id)
    if not product: fail_not_found("Produit")
    try:
        if db.scalar(select(func.count(PurchaseLine.id)).where(PurchaseLine.product_id == product_id)):
            raise HTTPException(409, "Ce produit figure encore dans un achat et ne peut pas être supprimé")
        db.execute(delete(StockMovement).where(StockMovement.product_id == product_id))
        db.delete(product); record_action(db, actor, "suppression", "produit", product_id); db.commit()
    except HTTPException:
        db.rollback(); raise
    except IntegrityError: db.rollback(); raise HTTPException(409, "Ce produit est utilisé dans un achat et ne peut pas être supprimé")


def loaded_purchase(db: Session, purchase_id: int) -> Purchase | None:
    return db.scalar(select(Purchase).options(selectinload(Purchase.lines), selectinload(Purchase.supplier)).where(Purchase.id == purchase_id))


def apply_purchase_stock(db: Session, purchase: Purchase, actor: User, quantities: dict[int, tuple[int, str | None]]) -> list[str]:
    details=[]
    for line in purchase.lines:
        received,line_comment=quantities.get(line.product_id,(0,None))
        if not received:continue
        product = db.get(Product, line.product_id)
        if not product: fail_not_found(f"Produit #{line.product_id}")
        previous=product.stock;product.stock+=received;line.received_quantity+=received
        comment=f"Réception {purchase.number}"+(f" · {line_comment}" if line_comment else "")
        db.add(StockMovement(product_id=line.product_id,type=MovementType.IN,movement_type=StockMovementType.PURCHASE_RECEIPT.value,quantity=received,reason="Entrée achat fournisseur",reference=purchase.number,user_id=actor.id,previous_stock=previous,new_stock=product.stock,reference_type="purchase",reference_id=purchase.id,comment=comment))
        details.append(f"produit {line.product_id}: +{received} ({line_comment or 'sans commentaire'})")
    return details


def set_purchase_lines(db: Session, purchase: Purchase, payload: PurchaseInput) -> None:
    if payload.status not in PURCHASE_STATUSES-{PurchaseStatus.RECEIVED}: raise HTTPException(422, "Statut d'achat invalide ou réception à effectuer via l'action Réceptionner")
    supplier=db.get(Supplier,payload.supplier_id) if payload.supplier_id else None
    if payload.supplier_id and (not supplier or supplier.status!="active"): raise HTTPException(400,"Fournisseur introuvable ou inactif")
    if payload.status!=PurchaseStatus.PREPARATION and not supplier:raise HTTPException(422,"Veuillez sélectionner un fournisseur")
    purchase.number=payload.number or f"ACH-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}";purchase.supplier_id=payload.supplier_id;purchase.client_id=None;purchase.status=payload.status;purchase.notes=payload.notes;purchase.purchase_date=payload.purchase_date or datetime.now();purchase.expected_delivery_date=payload.expected_delivery_date
    purchase.lines.clear(); subtotal = Decimal("0"); tax_amount=Decimal("0")
    for item in payload.lines:
        product = db.get(Product, item.product_id)
        if not product: fail_not_found(f"Produit #{item.product_id}")
        gross=item.unit_price*item.quantity;line_total=gross*(Decimal("1")-item.discount/Decimal("100"));tax=line_total*item.tax_rate/Decimal("100");line_ttc=line_total+tax;subtotal+=line_total;tax_amount+=tax
        purchase.lines.append(PurchaseLine(product_id=item.product_id,quantity=item.quantity,received_quantity=0,unit_price=item.unit_price,discount=item.discount,tax_rate=item.tax_rate,line_total=line_total,tax_amount=tax,total_amount=line_ttc))
        if payload.status!=PurchaseStatus.PREPARATION and supplier:
            supplier_price=db.scalar(select(SupplierProduct).where(SupplierProduct.supplier_id==supplier.id,SupplierProduct.product_id==item.product_id))
            if not supplier_price:
                supplier_price=SupplierProduct(supplier_id=supplier.id,product_id=item.product_id,purchase_price=item.unit_price)
                db.add(supplier_price)
            supplier_price.purchase_price=item.unit_price;supplier_price.last_purchase_date=purchase.purchase_date;supplier_price.is_active=True
    purchase.subtotal=subtotal;purchase.tax_amount=tax_amount;purchase.total=subtotal+tax_amount


@router.get("/suppliers", response_model=list[SupplierRead], tags=["Fournisseurs"])
def suppliers(q:str="",status:str|None=None,db:Session=Depends(get_db),_:User=Depends(PURCHASE_STAFF)):
    stmt=select(Supplier).order_by(Supplier.name)
    if q:
        term=f"%{q}%";stmt=stmt.where(or_(Supplier.name.ilike(term),Supplier.company_name.ilike(term),Supplier.email.ilike(term),Supplier.phone.ilike(term),Supplier.ice.ilike(term)))
    if status:stmt=stmt.where(Supplier.status==status)
    return list(db.scalars(stmt.limit(1000)))


@router.post("/suppliers",response_model=SupplierRead,status_code=201,tags=["Fournisseurs"])
def add_supplier(payload:SupplierInput,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    supplier=Supplier(**payload.model_dump());db.add(supplier);flush_or_conflict(db,"Un fournisseur avec cet ICE existe déjà");record_action(db,actor,"création","fournisseur",supplier.id);db.commit();db.refresh(supplier);return supplier


@router.put("/suppliers/{supplier_id}",response_model=SupplierRead,tags=["Fournisseurs"])
def edit_supplier(supplier_id:int,payload:SupplierInput,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    supplier=db.get(Supplier,supplier_id)
    if not supplier:fail_not_found("Fournisseur")
    for key,value in payload.model_dump().items():setattr(supplier,key,value)
    record_action(db,actor,"modification","fournisseur",supplier.id);commit_or_conflict(db,"Un fournisseur avec cet ICE existe déjà");db.refresh(supplier);return supplier


@router.patch("/suppliers/{supplier_id}/status",response_model=SupplierRead,tags=["Fournisseurs"])
def toggle_supplier(supplier_id:int,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    supplier=db.get(Supplier,supplier_id)
    if not supplier:fail_not_found("Fournisseur")
    supplier.status="inactive" if supplier.status=="active" else "active";record_action(db,actor,"changement statut","fournisseur",supplier.id);db.commit();db.refresh(supplier);return supplier


@router.get("/suppliers/{supplier_id}/purchases",response_model=list[PurchaseRead],tags=["Fournisseurs"])
def supplier_purchases(supplier_id:int,db:Session=Depends(get_db),_:User=Depends(PURCHASE_STAFF)):
    return list(db.scalars(select(Purchase).options(selectinload(Purchase.lines),selectinload(Purchase.supplier)).where(Purchase.supplier_id==supplier_id).order_by(Purchase.created_at.desc())))


@router.get("/purchases", response_model=list[PurchaseRead], tags=["Achats"])
def purchases(q: str = "", status: str | None = None, supplier_id: int | None = None, date: str | None = None, db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    stmt = select(Purchase).options(selectinload(Purchase.lines),selectinload(Purchase.supplier)).order_by(Purchase.created_at.desc())
    if q:
        term=f"%{q}%";stmt=stmt.outerjoin(Purchase.supplier).where(or_(Purchase.number.ilike(term),Supplier.name.ilike(term),Supplier.company_name.ilike(term)))
    if status: stmt = stmt.where(Purchase.status == status)
    if supplier_id: stmt = stmt.where(Purchase.supplier_id == supplier_id)
    if date: stmt=stmt.where(func.date(Purchase.purchase_date)==date)
    return list(db.scalars(stmt.limit(500)).unique())


@router.post("/purchases", response_model=PurchaseRead, status_code=201, tags=["Achats"])
def add_purchase(payload: PurchaseInput, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    purchase = Purchase(created_by=actor.id); set_purchase_lines(db, purchase, payload); db.add(purchase); flush_or_conflict(db, "Ce numéro d'achat existe déjà"); record_action(db, actor, "création", "achat fournisseur", purchase.id); commit_or_conflict(db, "Ce numéro d'achat existe déjà"); return loaded_purchase(db, purchase.id)


@router.put("/purchases/{purchase_id}", response_model=PurchaseRead, tags=["Achats"])
def edit_purchase(purchase_id: int, payload: PurchaseInput, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    purchase = loaded_purchase(db, purchase_id)
    if not purchase: fail_not_found("Achat")
    if purchase.status in {PurchaseStatus.RECEIVED,PurchaseStatus.CANCELLED}:raise HTTPException(409,"Cet achat ne peut plus être modifié")
    purchase.lines.clear()
    db.flush()
    set_purchase_lines(db, purchase, payload)
    db.flush()
    record_action(db, actor, "modification", "achat", purchase.id)
    commit_or_conflict(db, "Ce numéro d'achat existe déjà")
    return loaded_purchase(db, purchase.id)


@router.delete("/purchases/{purchase_id}", status_code=204, tags=["Achats"])
def remove_purchase(purchase_id: int, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    purchase = loaded_purchase(db, purchase_id)
    if not purchase: fail_not_found("Achat")
    if purchase.status==PurchaseStatus.RECEIVED:raise HTTPException(409,"Un achat reçu ne peut pas être supprimé")
    db.delete(purchase); record_action(db, actor, "suppression", "achat fournisseur", purchase_id); db.commit()


@router.patch("/purchases/{purchase_id}/supplier-confirmation",response_model=PurchaseRead,tags=["Achats"])
def confirm_supplier_delivery(purchase_id:int,payload:SupplierConfirmationInput,request:Request,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    purchase=loaded_purchase(db,purchase_id)
    if not purchase:fail_not_found("Achat")
    if purchase.status!=PurchaseStatus.SENT:raise HTTPException(409,"La confirmation fournisseur est disponible uniquement après l'envoi de la commande")
    previous=purchase.supplier_confirmed_delivery_date
    purchase.supplier_confirmed_delivery_date=payload.confirmed_delivery_date
    purchase.supplier_confirmation_reference=payload.confirmation_reference
    purchase.supplier_confirmation_contact=payload.contact_name
    purchase.supplier_confirmation_comment=payload.comment
    purchase.status=PurchaseStatus.CONFIRMED
    details=f"{purchase.number} · ancienne date: {previous or 'aucune'} · nouvelle date: {payload.confirmed_delivery_date} · référence: {payload.confirmation_reference or 'aucune'} · {payload.comment or 'sans commentaire'}"
    record_action(db,actor,"confirmation fournisseur","achat fournisseur",purchase.id,details,request.client.host if request.client else None);db.commit();return loaded_purchase(db,purchase.id)


@router.patch("/purchases/{purchase_id}/supplier-accepted",response_model=PurchaseRead,tags=["Achats"])
def supplier_accepted(purchase_id:int,payload:SupplierAcceptanceInput,request:Request,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    purchase=loaded_purchase(db,purchase_id)
    if not purchase:fail_not_found("Achat")
    if purchase.status!=PurchaseStatus.SENT:raise HTTPException(409,"Seule une commande envoyée peut être confirmée par le fournisseur")
    if not purchase.supplier_id or not purchase.supplier:raise HTTPException(422,"Le fournisseur associé est introuvable")
    if not purchase.lines:raise HTTPException(422,"La commande doit contenir au moins un produit")
    now=datetime.now();purchase.status=PurchaseStatus.CONFIRMED;purchase.supplier_accepted_at=now;purchase.supplier_accepted_by=actor.id;purchase.supplier_acceptance_comment=payload.comment;purchase.supplier_acceptance_reference=payload.reference
    details=f"{purchase.number} · {PurchaseStatus.SENT} → {PurchaseStatus.CONFIRMED} · référence: {payload.reference or 'aucune'} · {payload.comment or 'sans commentaire'}"
    record_action(db,actor,"confirmation fournisseur","achat fournisseur",purchase.id,details,request.client.host if request.client else None);db.commit();return loaded_purchase(db,purchase.id)


def transition_purchase(purchase_id:int,target:PurchaseStatus,request:Request,db:Session,actor:User)->Purchase:
    purchase=loaded_purchase(db,purchase_id)
    if not purchase:fail_not_found("Achat")
    allowed={(PurchaseStatus.PREPARATION,PurchaseStatus.SENT),(PurchaseStatus.PREPARATION,PurchaseStatus.CANCELLED),(PurchaseStatus.SENT,PurchaseStatus.CANCELLED),(PurchaseStatus.CONFIRMED,PurchaseStatus.CANCELLED)}
    if (purchase.status,target) not in allowed:raise HTTPException(409,"Cette action n'est pas disponible pour le statut actuel")
    if target==PurchaseStatus.SENT:
        if not purchase.supplier_id or not purchase.supplier:raise HTTPException(422,"Un fournisseur valide est requis")
        if not purchase.lines:raise HTTPException(422,"Ajoutez au moins un produit")
        if any(line.quantity<=0 or line.unit_price<=0 for line in purchase.lines):raise HTTPException(422,"Les quantités et prix doivent être supérieurs à zéro")
    old=purchase.status;purchase.status=target
    record_action(db,actor,"changement statut achat","achat fournisseur",purchase.id,f"{purchase.number} · {old} → {target}",request.client.host if request.client else None);db.commit();return loaded_purchase(db,purchase.id)


@router.patch("/purchases/{purchase_id}/send",response_model=PurchaseRead,tags=["Achats"])
def send_purchase(purchase_id:int,request:Request,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    return transition_purchase(purchase_id,PurchaseStatus.SENT,request,db,actor)


@router.patch("/purchases/{purchase_id}/cancel",response_model=PurchaseRead,tags=["Achats"])
def cancel_purchase(purchase_id:int,request:Request,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    return transition_purchase(purchase_id,PurchaseStatus.CANCELLED,request,db,actor)


@router.post("/purchases/{purchase_id}/receive",response_model=PurchaseRead,tags=["Achats"])
@router.patch("/purchases/{purchase_id}/receive",response_model=PurchaseRead,tags=["Achats"])
def receive_purchase(purchase_id:int,request:Request,payload:PurchaseReceptionInput|None=None,db:Session=Depends(get_db),actor:User=Depends(PURCHASE_STAFF)):
    purchase=loaded_purchase(db,purchase_id)
    if not purchase:fail_not_found("Achat")
    if purchase.status==PurchaseStatus.RECEIVED or purchase.received_at:raise HTTPException(409,"Cet achat a déjà été réceptionné")
    if purchase.status==PurchaseStatus.CANCELLED:raise HTTPException(409,"Un achat annulé ne peut pas être réceptionné")
    if purchase.status!=PurchaseStatus.CONFIRMED:raise HTTPException(409,"La commande doit être confirmée par le fournisseur avant sa réception")
    by_product={line.product_id:line for line in purchase.lines};quantities:dict[int,tuple[int,str|None]]={}
    if payload and payload.items is not None:
        if not payload.items:raise HTTPException(422,"Saisissez au moins une quantité reçue")
        for item in payload.items:
            if item.product_id in quantities:raise HTTPException(422,f"Le produit #{item.product_id} est présent plusieurs fois")
            line=by_product.get(item.product_id)
            if not line:raise HTTPException(422,f"Le produit #{item.product_id} ne fait pas partie de cette commande")
            remaining=line.quantity-line.received_quantity
            if item.received_quantity>remaining:raise HTTPException(422,f"La quantité reçue du produit #{item.product_id} dépasse la quantité restante ({remaining})")
            quantities[item.product_id]=(item.received_quantity,item.comment)
    else:quantities={line.product_id:(line.quantity-line.received_quantity,None) for line in purchase.lines if line.quantity>line.received_quantity}
    if not quantities:raise HTTPException(409,"Aucune quantité ne reste à réceptionner")
    old_status=purchase.status
    try:
        item_details=apply_purchase_stock(db,purchase,actor,quantities)
        now=datetime.now();purchase.status=PurchaseStatus.RECEIVED;purchase.actual_reception_date=now;purchase.received_at=now;purchase.received_by=actor.id;purchase.reception_comment=payload.comment if payload else None
        details=f"{purchase.number} · {old_status} → {purchase.status} · "+"; ".join(item_details)+(f" · {payload.comment}" if payload and payload.comment else "")
        record_action(db,actor,"réception fournisseur","achat fournisseur",purchase.id,details,request.client.host if request.client else None);db.commit()
    except Exception:
        db.rollback();raise
    return loaded_purchase(db,purchase.id)


@router.get("/stock/movements", response_model=list[MovementRead], tags=["Stock"])
def movements(q: str = "", movement_type: StockMovementType | None = None, product_id: int | None = None, date: str | None = None, user_id: int | None = None, source_type: str | None = None, db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    stmt = select(StockMovement).order_by(StockMovement.created_at.desc())
    if q: stmt = stmt.where(or_(StockMovement.reason.ilike(f"%{q}%"), StockMovement.reference.ilike(f"%{q}%")))
    if movement_type: stmt = stmt.where(StockMovement.movement_type == movement_type.value)
    if product_id: stmt = stmt.where(StockMovement.product_id == product_id)
    if date: stmt = stmt.where(func.date(StockMovement.created_at) == date)
    if user_id: stmt = stmt.where(StockMovement.user_id == user_id)
    if source_type: stmt = stmt.where(StockMovement.reference_type == source_type)
    return list(db.scalars(stmt.limit(1000)))


@router.post("/stock/movements", response_model=MovementRead, status_code=201, tags=["Stock"])
def add_movement(payload: MovementInput, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    product = db.get(Product, payload.product_id)
    if not product: fail_not_found("Produit")
    if payload.movement_type == StockMovementType.POSITIVE_ADJUSTMENT:
        delta, legacy_type = payload.quantity, MovementType.IN
    elif payload.movement_type in {StockMovementType.NEGATIVE_ADJUSTMENT, StockMovementType.DAMAGED_PRODUCT}:
        delta, legacy_type = -payload.quantity, MovementType.OUT
    elif payload.movement_type == StockMovementType.INVENTORY:
        delta, legacy_type = payload.quantity - product.stock, MovementType.ADJUSTMENT
    else:
        raise HTTPException(422, "Ce type de mouvement est réservé aux opérations automatiques")
    if product.stock + delta < 0: raise HTTPException(409, f"Stock insuffisant : {product.stock} unité(s) disponible(s)")
    previous = product.stock; product.stock += delta
    movement = StockMovement(product_id=payload.product_id, type=legacy_type, movement_type=payload.movement_type.value, quantity=payload.quantity, reason=payload.reason.strip(), comment=payload.comment, user_id=actor.id, previous_stock=previous, new_stock=product.stock, reference_type="manual_adjustment")
    db.add(movement); db.flush(); record_action(db, actor, "ajustement stock", "produit", product.id, f"{payload.movement_type.value}: {payload.quantity}"); db.commit(); db.refresh(movement); return movement


@router.get("/dashboard", response_model=DashboardRead, tags=["Dashboard"])
def dashboard(db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    recent = list(db.scalars(select(Purchase).options(selectinload(Purchase.lines)).order_by(Purchase.created_at.desc()).limit(8)))
    today = datetime.now().astimezone().date()
    day_start = datetime.combine(today, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    validated_statuses = (OrderStatus.APPROVED, OrderStatus.IN_PREPARATION, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CONFIRMED, OrderStatus.PREPARED)
    process_statuses = (OrderStatus.PENDING, OrderStatus.APPROVED, OrderStatus.IN_PREPARATION)
    process_priority = {OrderStatus.PENDING: 0, OrderStatus.APPROVED: 1, OrderStatus.IN_PREPARATION: 2}
    process_orders = list(db.scalars(select(CustomerOrder).options(selectinload(CustomerOrder.client)).where(CustomerOrder.status.in_(process_statuses)).order_by(CustomerOrder.created_at.desc()).limit(100)))
    process_orders.sort(key=lambda order: (process_priority[order.status], -order.created_at.timestamp()))
    latest_orders = list(db.scalars(select(CustomerOrder).options(selectinload(CustomerOrder.client)).order_by(CustomerOrder.created_at.desc()).limit(8)))

    def order_summary(order: CustomerOrder) -> dict:
        next_actions = {OrderStatus.PENDING: "APPROUVER_OU_REFUSER", OrderStatus.APPROVED: "PREPARER", OrderStatus.IN_PREPARATION: "EXPEDIER"}
        return {"id":order.id, "order_number":order.number, "client_name":order.client.name if order.client else f"Client #{order.client_id}", "created_at":order.created_at, "total_amount":order.total, "status":order.status.value, "next_action":next_actions.get(order.status)}

    order_counts={status:int(count) for status,count in db.execute(select(CustomerOrder.status,func.count(CustomerOrder.id)).group_by(CustomerOrder.status))}
    purchase_counts={str(status):int(count) for status,count in db.execute(select(Purchase.status,func.count(Purchase.id)).group_by(Purchase.status))}
    approved_today=db.scalar(select(func.count(CustomerOrder.id)).where(CustomerOrder.status==OrderStatus.APPROVED,CustomerOrder.approved_at>=day_start,CustomerOrder.approved_at<day_end)) or 0
    receptions_today=db.scalar(select(func.count(Purchase.id)).where(Purchase.status==PurchaseStatus.RECEIVED,Purchase.actual_reception_date>=day_start,Purchase.actual_reception_date<day_end)) or 0
    stats=dict(total_orders=sum(order_counts.values()),pending_orders=order_counts.get(OrderStatus.PENDING,0),approved_orders=order_counts.get(OrderStatus.APPROVED,0),approved_today=approved_today,in_preparation=order_counts.get(OrderStatus.IN_PREPARATION,0),shipped_orders=order_counts.get(OrderStatus.SHIPPED,0),delivered_orders=order_counts.get(OrderStatus.DELIVERED,0),rejected_orders=order_counts.get(OrderStatus.REJECTED,0),total_purchases=sum(purchase_counts.values()),purchases_in_preparation=purchase_counts.get(PurchaseStatus.PREPARATION.value,0),purchases_sent=purchase_counts.get(PurchaseStatus.SENT.value,0),purchases_confirmed=purchase_counts.get(PurchaseStatus.CONFIRMED.value,0),purchases_received=purchase_counts.get(PurchaseStatus.RECEIVED.value,0),receptions_today=receptions_today)
    logger.info("Dashboard SQL counters orders=%s purchases=%s computed=%s",{getattr(key,'name',str(key)):value for key,value in order_counts.items()},purchase_counts,stats)
    return DashboardRead(
        products_count=db.scalar(select(func.count(Product.id))) or 0,
        clients_count=db.scalar(select(func.count(Client.id))) or 0,
        total_stock=db.scalar(select(func.coalesce(func.sum(Product.stock), 0))) or 0,
        low_stock_count=db.scalar(select(func.count(Product.id)).where(Product.stock <= Product.minimum_stock)) or 0,
        recent_purchases=recent,
        **stats,
        approved_amount=db.scalar(select(func.coalesce(func.sum(CustomerOrder.total), 0)).where(CustomerOrder.status.in_(validated_statuses))) or Decimal("0"),
        orders_to_process=[order_summary(order) for order in process_orders[:20]],
        recent_orders=[order_summary(order) for order in latest_orders],
    )


def require_linked_client(user: User) -> int:
    if not user.client_id:
        raise HTTPException(403, "Votre compte n'est pas encore lié à une fiche client. Contactez l'administrateur.")
    if not user.client or user.client.status != "active":
        raise HTTPException(403, "Votre fiche client n'est pas active")
    return user.client_id


def order_query(order_id: int | None = None):
    stmt = select(CustomerOrder).options(selectinload(CustomerOrder.lines), selectinload(CustomerOrder.client)).order_by(CustomerOrder.created_at.desc())
    return stmt.where(CustomerOrder.id == order_id) if order_id is not None else stmt


@router.get("/client/orders", response_model=list[CustomerOrderRead], tags=["Espace client"])
def my_orders(db: Session = Depends(get_db), user: User = Depends(CLIENT_ONLY)):
    client_id = require_linked_client(user)
    return list(db.scalars(order_query().where(CustomerOrder.client_id == client_id).limit(500)))


@router.get("/client/orders/{order_id}", response_model=CustomerOrderRead, tags=["Espace client"])
def my_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(CLIENT_ONLY)):
    client_id = require_linked_client(user)
    order = db.scalar(order_query(order_id).where(CustomerOrder.client_id == client_id))
    if not order: fail_not_found("Commande")
    return order


@router.post("/client/orders", response_model=CustomerOrderRead, status_code=201, tags=["Espace client"])
def create_customer_order(payload: CustomerOrderInput, db: Session = Depends(get_db), user: User = Depends(CLIENT_ONLY)):
    client_id = require_linked_client(user)
    quantities: dict[int, int] = {}
    for requested in payload.lines:
        quantities[requested.product_id] = quantities.get(requested.product_id, 0) + requested.quantity
    order = CustomerOrder(number=f"CMD-{datetime.now():%Y%m%d}-{uuid4().hex[:8].upper()}", client_id=client_id, user_id=user.id, status=OrderStatus.PENDING)
    total = Decimal("0")
    for product_id, quantity in quantities.items():
        product = db.get(Product, product_id)
        if not product or product.status != "active": raise HTTPException(400, f"Le produit #{product_id} n'est plus disponible")
        if product.stock < quantity: raise HTTPException(409, f"Stock insuffisant pour {product.name} : {product.stock} disponible(s)")
        line_total = product.price * quantity; total += line_total
        order.lines.append(CustomerOrderLine(product_id=product.id, product_name=product.name, product_reference=product.reference, quantity=quantity, unit_price=product.price, line_total=line_total))
    order.total = total; db.add(order); flush_or_conflict(db, "Impossible de générer le numéro de commande"); record_action(db, user, "création", "commande", order.id, order.number); db.commit()
    return db.scalar(order_query(order.id))


@router.patch("/orders/{order_id}/status", response_model=CustomerOrderRead, tags=["Commandes"])
def update_order_status(order_id: int, status: OrderStatus, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    order = db.scalar(order_query(order_id))
    if not order: fail_not_found("Commande")
    order.status = status; record_action(db, actor, "statut", "commande", order.id, status.value); db.commit(); db.refresh(order); return order


@router.get("/orders", response_model=list[CustomerOrderRead], tags=["Commandes"])
def all_orders(q: str = "", status: OrderStatus | None = None, date: str | None = None, db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    """Liste globale réservée aux services Achats et Administration."""
    stmt = order_query()
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.join(CustomerOrder.client).where(or_(CustomerOrder.number.ilike(term), Client.name.ilike(term), Client.company_name.ilike(term)))
    if status: stmt = stmt.where(CustomerOrder.status == status)
    if date:
        try:
            selected = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, "La date doit être au format AAAA-MM-JJ")
        stmt = stmt.where(func.date(CustomerOrder.created_at) == selected.isoformat())
    return list(db.scalars(stmt.limit(1000)).unique())


@router.get("/orders/{order_id}", response_model=CustomerOrderRead, tags=["Commandes"])
def staff_order(order_id: int, db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    order = db.scalar(order_query(order_id))
    if not order: fail_not_found("Commande")
    return order


@router.patch("/orders/{order_id}/approve", tags=["Commandes"])
def approve_order(order_id: int, payload: OrderApprovalInput, request: Request, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    """Approuve atomiquement une demande et ne décrémente le stock qu'une seule fois."""
    order = db.scalar(order_query(order_id))
    if not order: fail_not_found("Commande")
    if order.status != OrderStatus.PENDING: raise HTTPException(409, "Seule une commande en attente peut être approuvée")
    products: dict[int, Product] = {}
    for line in order.lines:
        product = db.get(Product, line.product_id)
        if not product: raise HTTPException(409, f"Le produit {line.product_reference} n'existe plus")
        if product.stock < line.quantity: raise HTTPException(409, f"Stock insuffisant pour {product.name} : {product.stock} disponible(s), {line.quantity} demandé(s)")
        products[line.product_id] = product
    for line in order.lines:
        product = products[line.product_id]; previous=product.stock;product.stock -= line.quantity
        db.add(StockMovement(product_id=product.id, type=MovementType.OUT, movement_type=StockMovementType.CUSTOMER_ORDER.value, quantity=line.quantity, reason=f"Sortie commande client {order.number}", reference=order.number, user_id=actor.id, previous_stock=previous, new_stock=product.stock, reference_type="customer_order", reference_id=order.id, comment=f"Commande approuvée {order.number}"))
    order.status = OrderStatus.APPROVED; order.approved_at = datetime.now(); order.approved_by = actor.id; order.purchase_comment = payload.comment or None
    record_action(db, actor, "approbation", "commande", order.id, f"{order.number} · {payload.comment or 'Sans commentaire'}", request.client.host if request.client else None)
    db.commit()
    return {"message":"Commande approuvée", "status":OrderStatus.APPROVED.value}


@router.patch("/orders/{order_id}/reject", tags=["Commandes"])
def reject_order(order_id: int, payload: OrderRejectionInput, request: Request, db: Session = Depends(get_db), actor: User = Depends(PURCHASE_STAFF)):
    """Refuse une demande sans modifier le stock."""
    order = db.scalar(order_query(order_id))
    if not order: fail_not_found("Commande")
    if order.status != OrderStatus.PENDING: raise HTTPException(409, "Seule une commande en attente peut être refusée")
    order.status = OrderStatus.REJECTED; order.rejected_at = datetime.now(); order.rejected_by = actor.id; order.rejection_reason = payload.reason.strip(); order.purchase_comment = payload.comment or None
    record_action(db, actor, "refus", "commande", order.id, f"{order.number} · {order.rejection_reason}", request.client.host if request.client else None)
    db.commit()
    return {"message":"Commande refusée", "status":OrderStatus.REJECTED.value}


@router.get("/audit", response_model=list[AuditRead], tags=["Journal"])
def audit(q: str = "", limit: int = Query(300, le=1000), db: Session = Depends(get_db), _: User = Depends(ADMIN)):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if q: stmt = stmt.where(or_(AuditLog.action.ilike(f"%{q}%"), AuditLog.entity.ilike(f"%{q}%"), AuditLog.details.ilike(f"%{q}%")))
    return list(db.scalars(stmt.limit(limit)))


def excel_response(title: str, headers: list[str], rows: list, filename: str):
    book = Workbook(); sheet = book.active; sheet.title = title; sheet.append(headers)
    for row in rows: sheet.append([float(v) if isinstance(v, Decimal) else v for v in row])
    output = BytesIO(); book.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/reports/stock.xlsx", tags=["Rapports"])
def stock_excel(db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    rows = list(db.execute(select(Product.reference, Product.name, Product.stock, Product.minimum_stock, Product.price).order_by(Product.name)))
    return excel_response("Stock", ["Référence", "Produit", "Stock", "Seuil", "Prix"], rows, "stock-soremed.xlsx")


@router.get("/reports/clients.xlsx", tags=["Rapports"])
def clients_excel(db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    rows = list(db.execute(select(Client.name, Client.company_name, Client.ice, Client.rc, Client.city, Client.phone, Client.email, Client.status).order_by(Client.name)))
    return excel_response("Clients", ["Nom", "Raison sociale", "ICE", "RC", "Ville", "Téléphone", "Email", "Statut"], rows, "clients-soremed.xlsx")


@router.get("/reports/purchases.xlsx", tags=["Rapports"])
def purchases_excel(db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    rows = list(db.execute(select(Purchase.number, Purchase.created_at, Purchase.client_id, Purchase.status, Purchase.total).order_by(Purchase.created_at.desc())))
    return excel_response("Achats", ["Numéro", "Date", "Client", "Statut", "Total"], rows, "achats-soremed.xlsx")


@router.get("/reports/stock.pdf", tags=["Rapports"])
def stock_pdf(db: Session = Depends(get_db), _: User = Depends(PURCHASE_STAFF)):
    rows = list(db.execute(select(Product.reference, Product.name, Product.stock, Product.minimum_stock, Product.price).order_by(Product.name)))
    output = BytesIO(); pdf = canvas.Canvas(output, pagesize=A4); y = 800; pdf.setTitle("Rapport de stock SOREMED"); pdf.setFont("Helvetica-Bold", 15); pdf.drawString(40, y, "SOREMED - Rapport de stock"); y -= 30; pdf.setFont("Helvetica", 9)
    for ref, name, stock, minimum, price in rows:
        pdf.drawString(40, y, f"{ref} | {name[:45]} | Stock: {stock} | Seuil: {minimum} | {price} MAD"); y -= 16
        if y < 50: pdf.showPage(); pdf.setFont("Helvetica", 9); y = 800
    pdf.save(); output.seek(0)
    return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=stock-soremed.pdf"})


@router.get("/settings", response_model=CompanyRead, tags=["Paramètres"])
def company(db: Session = Depends(get_db), _: User = Depends(ADMIN)):
    item = db.get(CompanySetting, 1)
    if not item: item = CompanySetting(id=1, company_name="SOREMED"); db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/settings", response_model=CompanyRead, tags=["Paramètres"])
def edit_company(payload: CompanyInput, db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    item = db.get(CompanySetting, 1) or CompanySetting(id=1)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    db.add(item); record_action(db, actor, "modification", "paramètres", 1); db.commit(); db.refresh(item); return item


@router.post("/settings/logo", response_model=CompanyRead, tags=["Paramètres"])
def company_logo(logo: UploadFile = File(...), db: Session = Depends(get_db), actor: User = Depends(ADMIN)):
    if logo.content_type not in {"image/jpeg", "image/png", "image/webp"}: raise HTTPException(400, "Format accepté : JPG, PNG ou WebP")
    suffix = {"image/jpeg":".jpg", "image/png":".png", "image/webp":".webp"}[logo.content_type]; folder = Path(settings.upload_dir).resolve() / "company"; folder.mkdir(parents=True, exist_ok=True); name = f"logo-{uuid4().hex}{suffix}"
    with (folder / name).open("wb") as output: shutil.copyfileobj(logo.file, output)
    item = db.get(CompanySetting, 1) or CompanySetting(id=1, company_name="SOREMED"); item.logo_path = f"/uploads/company/{name}"; db.add(item); record_action(db, actor, "logo", "paramètres", 1); db.commit(); db.refresh(item); return item


@router.get("/settings/backup", tags=["Paramètres"])
def backup_database(actor: User = Depends(ADMIN)):
    source = sqlite_path(); folder = Path(settings.backup_dir).resolve(); folder.mkdir(parents=True, exist_ok=True); target = folder / f"soremed-{datetime.now():%Y%m%d-%H%M%S}.db"
    engine.dispose()
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst: src.backup(dst)
    return FileResponse(target, media_type="application/x-sqlite3", filename=target.name)


@router.post("/settings/restore", tags=["Paramètres"])
def restore_database(backup: UploadFile = File(...), actor: User = Depends(ADMIN)):
    if not backup.filename or not backup.filename.lower().endswith((".db", ".sqlite", ".sqlite3")): raise HTTPException(400, "Sélectionnez une sauvegarde SQLite valide")
    folder = Path(settings.backup_dir).resolve(); folder.mkdir(parents=True, exist_ok=True); temporary = folder / f"restore-{uuid4().hex}.db"
    with temporary.open("wb") as output: shutil.copyfileobj(backup.file, output)
    try:
        with closing(sqlite3.connect(temporary)) as check:
            tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"users", "products", "clients"}.issubset(tables): raise HTTPException(400, "Le fichier ne correspond pas à une sauvegarde SOREMED")
        target = sqlite_path(); engine.dispose()
        with closing(sqlite3.connect(temporary)) as src, closing(sqlite3.connect(target)) as dst: src.backup(dst)
    finally:
        temporary.unlink(missing_ok=True)
    return {"message": "Base restaurée avec succès. Reconnectez-vous."}
