"""Contrats Pydantic exposés par l'API."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models.entities import ApprovalStatus, MovementType, Role, StockMovementType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ClientRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=30)
    password: str = Field(min_length=8)
    password_confirmation: str = Field(min_length=8)
    company_name: str | None = None
    ice: str | None = None
    rc: str | None = None
    address: str | None = None
    city: str | None = None
    accepted_terms: bool

    @model_validator(mode="after")
    def validate_registration(self):
        if self.password != self.password_confirmation:
            raise ValueError("Les mots de passe ne correspondent pas")
        if not self.accepted_terms:
            raise ValueError("Vous devez accepter les conditions d'utilisation")
        return self


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.CLIENT
    client_id: int | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)
    client_id: int | None = None


class UserClientSummary(ORMModel):
    id: int
    name: str
    company_name: str | None = None
    phone: str | None = None
    city: str | None = None
    status: str


class UserRead(ORMModel):
    id: int
    full_name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime
    client_id: int | None = None
    approval_status: ApprovalStatus
    approved_at: datetime | None = None
    approved_by: int | None = None
    client: UserClientSummary | None = None


class ClientInput(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    company_name: str | None = None
    ice: str | None = None
    rc: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    status: str = "active"


class ClientRead(ClientInput, ORMModel):
    id: int
    created_at: datetime


class ProductInput(BaseModel):
    reference: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=2, max_length=160)
    commercial_name: str | None = Field(default=None, max_length=180)
    active_ingredient: str | None = Field(default=None, max_length=180)
    description: str | None = None
    price: Decimal = Field(ge=0)
    default_purchase_price: Decimal | None = Field(default=None, ge=0)
    photo_path: str | None = None
    category_id: int | None = None
    stock: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=0, ge=0)
    barcode: str | None = None
    status: str = "active"
    laboratory: str | None = None
    dosage: str | None = None
    pharmaceutical_form: str | None = None
    packaging: str | None = None


class ProductRead(ProductInput, ORMModel):
    id: int
    created_at: datetime


class CategoryInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class CategoryRead(CategoryInput, ORMModel):
    id: int


class SupplierInput(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    company_name: str | None = None
    ice: str | None = None
    rc: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    primary_contact: str | None = None
    status: str = "active"


class SupplierRead(SupplierInput, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class PurchaseLineInput(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=0, ge=0, le=100)
    tax_rate: Decimal = Field(default=0, ge=0, le=100)


class PurchaseInput(BaseModel):
    number: str | None = Field(default=None, max_length=50)
    supplier_id: int | None = None
    status: str = "EN_PREPARATION"
    purchase_date: datetime | None = None
    expected_delivery_date: datetime | None = None
    notes: str | None = None
    lines: list[PurchaseLineInput] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def migrate_legacy_status(cls, value: str) -> str:
        """Accepte les anciens clients API mais ne persiste que les cinq statuts officiels."""
        return {"draft":"EN_PREPARATION","ordered":"COMMANDE_ENVOYEE","supplier_accepted":"CONFIRMEE_PAR_FOURNISSEUR","supplier_confirmed":"CONFIRMEE_PAR_FOURNISSEUR","awaiting_receipt":"CONFIRMEE_PAR_FOURNISSEUR","partially_received":"CONFIRMEE_PAR_FOURNISSEUR","received":"RECEPTIONNEE","cancelled":"ANNULEE"}.get(value,value)

    @model_validator(mode="after")
    def validate_purchase(self):
        ids=[line.product_id for line in self.lines]
        if len(ids)!=len(set(ids)):raise ValueError("Un produit ne peut apparaître qu'une seule fois dans l'achat")
        if self.status!="EN_PREPARATION":
            if not self.supplier_id:raise ValueError("Veuillez sélectionner un fournisseur")
            if not self.lines:raise ValueError("Ajoutez au moins un produit")
            if any(line.unit_price <= 0 for line in self.lines):raise ValueError("Le prix d'achat doit être supérieur à zéro")
        return self


class SupplierConfirmationInput(BaseModel):
    confirmed_delivery_date: datetime
    confirmation_reference: str | None = Field(default=None, max_length=100)
    contact_name: str | None = Field(default=None, max_length=150)
    comment: str | None = Field(default=None, max_length=2000)


class SupplierAcceptanceInput(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)
    reference: str | None = Field(default=None, max_length=100)


class PurchaseReceptionItemInput(BaseModel):
    product_id: int
    received_quantity: int = Field(gt=0)
    comment: str | None = Field(default=None, max_length=1000)


class PurchaseReceptionInput(BaseModel):
    items: list[PurchaseReceptionItemInput] | None = None
    comment: str | None = Field(default=None, max_length=2000)


class PurchaseLineRead(ORMModel):
    id: int
    product_id: int
    quantity: int
    received_quantity: int
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    line_total: Decimal
    tax_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")


class PurchasePriceRead(BaseModel):
    product_id: int
    supplier_id: int | None
    purchase_price: Decimal | None
    source: str


class PurchaseRead(ORMModel):
    id: int
    number: str
    supplier_id: int | None
    supplier: SupplierRead | None = None
    status: str
    purchase_date: datetime
    expected_delivery_date: datetime | None
    supplier_confirmed_delivery_date: datetime | None = None
    actual_reception_date: datetime | None = None
    supplier_confirmation_reference: str | None = None
    supplier_confirmation_contact: str | None = None
    supplier_confirmation_comment: str | None = None
    supplier_accepted_at: datetime | None = None
    supplier_acceptance_comment: str | None = None
    supplier_acceptance_reference: str | None = None
    supplier_accepted_by: int | None = None
    received_at: datetime | None
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    notes: str | None
    created_by: int | None
    received_by: int | None
    reception_comment: str | None = None
    created_at: datetime
    lines: list[PurchaseLineRead]


class MovementInput(BaseModel):
    product_id: int
    movement_type: StockMovementType
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=2)
    comment: str | None = None


class MovementRead(ORMModel):
    id: int
    product_id: int
    type: MovementType
    movement_type: str
    quantity: int
    reason: str
    reference: str | None = None
    user_id: int | None
    previous_stock: int | None = None
    new_stock: int | None = None
    reference_type: str | None = None
    reference_id: int | None = None
    comment: str | None = None
    created_at: datetime


class DashboardOrderRead(BaseModel):
    id: int
    order_number: str
    client_name: str
    created_at: datetime
    total_amount: Decimal
    status: str
    next_action: str | None = None


class DashboardRead(BaseModel):
    products_count: int
    clients_count: int
    total_stock: int
    low_stock_count: int
    recent_purchases: list[PurchaseRead]
    total_purchases: int
    purchases_in_preparation: int
    purchases_sent: int
    purchases_confirmed: int
    purchases_received: int
    receptions_today: int
    total_orders: int
    pending_orders: int
    approved_orders: int
    approved_today: int
    in_preparation: int
    shipped_orders: int
    delivered_orders: int
    rejected_orders: int
    approved_amount: Decimal
    orders_to_process: list[DashboardOrderRead]
    recent_orders: list[DashboardOrderRead]


class AuditRead(ORMModel):
    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: str | None
    details: str | None
    ip_address: str | None
    created_at: datetime


class CompanyInput(BaseModel):
    company_name: str = Field(min_length=2, max_length=180)
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None


class CompanyRead(CompanyInput, ORMModel):
    id: int
    logo_path: str | None = None


class CustomerOrderLineInput(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=10000)


class CustomerOrderInput(BaseModel):
    lines: list[CustomerOrderLineInput] = Field(min_length=1)


class OrderApprovalInput(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class OrderRejectionInput(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)
    comment: str | None = Field(default=None, max_length=2000)


class CustomerOrderLineRead(ORMModel):
    id: int
    product_id: int
    product_name: str
    product_reference: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class CustomerOrderRead(ORMModel):
    id: int
    number: str
    client_id: int
    user_id: int | None = None
    status: str
    total: Decimal
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    approved_by: int | None = None
    rejected_at: datetime | None = None
    rejected_by: int | None = None
    rejection_reason: str | None = None
    purchase_comment: str | None = None
    client: ClientRead | None = None
    lines: list[CustomerOrderLineRead]


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)
