"""Entités SQLAlchemy et relations du domaine SOREMED."""
from __future__ import annotations
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base


class Role(str, enum.Enum):
    ADMIN = "admin"
    PURCHASES = "achats"
    CLIENT = "client"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MovementType(str, enum.Enum):
    IN = "in"
    OUT = "out"
    ADJUSTMENT = "adjustment"


class StockMovementType(str, enum.Enum):
    """Nature métier d'un mouvement, distincte du sens historique."""
    PURCHASE_RECEIPT = "ENTREE_ACHAT"
    CUSTOMER_ORDER = "SORTIE_COMMANDE_CLIENT"
    POSITIVE_ADJUSTMENT = "AJUSTEMENT_POSITIF"
    NEGATIVE_ADJUSTMENT = "AJUSTEMENT_NEGATIF"
    CUSTOMER_RETURN = "RETOUR_CLIENT"
    DAMAGED_PRODUCT = "PRODUIT_ENDOMMAGE"
    INVENTORY = "INVENTAIRE"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PREPARATION = "in_preparation"
    SHIPPED = "shipped"
    CONFIRMED = "confirmed"
    PREPARED = "prepared"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.CLIENT, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), unique=True, index=True)
    approval_status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.APPROVED, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    client: Mapped[Client | None] = relationship(back_populates="user")


class Client(TimestampMixin, Base):
    __tablename__ = "clients"
    __table_args__ = (Index("ix_clients_city_status", "city", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    company_name: Mapped[str | None] = mapped_column(String(180))
    ice: Mapped[str | None] = mapped_column(String(30), unique=True)
    rc: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    purchases: Mapped[list[Purchase]] = relationship(back_populates="client")
    user: Mapped[User | None] = relationship(back_populates="client", uselist=False)
    orders: Mapped[list[CustomerOrder]] = relationship(back_populates="client")


class Supplier(TimestampMixin, Base):
    """Partenaire auprès duquel l'entreprise réalise ses approvisionnements."""
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    company_name: Mapped[str | None] = mapped_column(String(180))
    ice: Mapped[str | None] = mapped_column(String(30), unique=True)
    rc: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    primary_contact: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    purchases: Mapped[list[Purchase]] = relationship(back_populates="supplier")
    product_prices: Mapped[list[SupplierProduct]] = relationship(back_populates="supplier", cascade="all, delete-orphan")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_stock_threshold", "stock", "minimum_stock"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    commercial_name: Mapped[str | None] = mapped_column(String(180), index=True)
    active_ingredient: Mapped[str | None] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    default_purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    photo_path: Mapped[str | None] = mapped_column(String(300))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    minimum_stock: Mapped[int] = mapped_column(Integer, default=0)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    laboratory: Mapped[str | None] = mapped_column(String(160), index=True)
    dosage: Mapped[str | None] = mapped_column(String(100), index=True)
    pharmaceutical_form: Mapped[str | None] = mapped_column(String(100), index=True)
    packaging: Mapped[str | None] = mapped_column(String(160))
    category: Mapped[Category | None] = relationship(back_populates="products")
    purchase_lines: Mapped[list[PurchaseLine]] = relationship(back_populates="product")
    supplier_prices: Mapped[list[SupplierProduct]] = relationship(back_populates="product", cascade="all, delete-orphan")
    movements: Mapped[list[StockMovement]] = relationship(back_populates="product")


class Favorite(Base):
    """Produit favori privé d'un compte client."""
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    product: Mapped[Product] = relationship()


class Purchase(TimestampMixin, Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="EN_PREPARATION", index=True)
    purchase_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supplier_confirmed_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    actual_reception_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    supplier_confirmation_reference: Mapped[str | None] = mapped_column(String(100))
    supplier_confirmation_contact: Mapped[str | None] = mapped_column(String(150))
    supplier_confirmation_comment: Mapped[str | None] = mapped_column(Text)
    supplier_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    supplier_acceptance_comment: Mapped[str | None] = mapped_column(Text)
    supplier_acceptance_reference: Mapped[str | None] = mapped_column(String(100))
    supplier_accepted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    reception_comment: Mapped[str | None] = mapped_column(Text)
    client: Mapped[Client | None] = relationship(back_populates="purchases")
    supplier: Mapped[Supplier | None] = relationship(back_populates="purchases")
    lines: Mapped[list[PurchaseLine]] = relationship(back_populates="purchase", cascade="all, delete-orphan")


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"
    __table_args__ = (UniqueConstraint("purchase_id", "product_id", name="uq_purchase_product"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    purchase: Mapped[Purchase] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(back_populates="purchase_lines")


class SupplierProduct(TimestampMixin, Base):
    """Dernier tarif connu d'un produit chez un fournisseur donné."""
    __tablename__ = "supplier_products"
    __table_args__ = (UniqueConstraint("supplier_id", "product_id", name="uq_supplier_product"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    supplier_reference: Mapped[str | None] = mapped_column(String(100))
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, default=1)
    last_purchase_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    supplier: Mapped[Supplier] = relationship(back_populates="product_prices")
    product: Mapped[Product] = relationship(back_populates="supplier_prices")


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    type: Mapped[MovementType] = mapped_column(Enum(MovementType), index=True)
    movement_type: Mapped[str] = mapped_column(String(40), default=StockMovementType.INVENTORY.value, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    reference: Mapped[str | None] = mapped_column(String(80), index=True)
    previous_stock: Mapped[int | None] = mapped_column(Integer)
    new_stock: Mapped[int | None] = mapped_column(Integer)
    reference_type: Mapped[str | None] = mapped_column(String(40), index=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    product: Mapped[Product] = relationship(back_populates="movements")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ChatMessage(Base):
    """Historique privé et limité des échanges avec l'assistant local."""
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(60), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CompanySetting(Base):
    __tablename__ = "company_settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    company_name: Mapped[str] = mapped_column(String(180), default="SOREMED")
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    logo_path: Mapped[str | None] = mapped_column(String(300))


class CustomerOrder(TimestampMixin, Base):
    """Commande passée par un utilisateur client depuis le catalogue."""
    __tablename__ = "customer_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    purchase_comment: Mapped[str | None] = mapped_column(Text)
    client: Mapped[Client] = relationship(back_populates="orders")
    lines: Mapped[list[CustomerOrderLine]] = relationship(back_populates="order", cascade="all, delete-orphan")


class CustomerOrderLine(Base):
    """Ligne figée d'une commande avec prix issu exclusivement du catalogue."""
    __tablename__ = "customer_order_lines"
    __table_args__ = (UniqueConstraint("order_id", "product_id", name="uq_customer_order_product"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    product_name: Mapped[str] = mapped_column(String(160))
    product_reference: Mapped[str] = mapped_column(String(60))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    order: Mapped[CustomerOrder] = relationship(back_populates="lines")
