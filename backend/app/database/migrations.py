"""Migrations légères non destructives exécutées avant la création des tables SQLite."""
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def migrate_sqlite(engine: Engine) -> None:
    """Ajoute les colonnes requises aux bases existantes sans effacer les données."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "products" in inspector.get_table_names():
        product_columns={column["name"] for column in inspector.get_columns("products")}
        with engine.begin() as connection:
            for name,sql_type in {"laboratory":"VARCHAR(160)","dosage":"VARCHAR(100)","pharmaceutical_form":"VARCHAR(100)","packaging":"VARCHAR(160)","commercial_name":"VARCHAR(180)","active_ingredient":"VARCHAR(180)","default_purchase_price":"NUMERIC(12,2)"}.items():
                if name not in product_columns: connection.execute(text(f"ALTER TABLE products ADD COLUMN {name} {sql_type}"))
            connection.execute(text("UPDATE products SET commercial_name=name WHERE commercial_name IS NULL OR trim(commercial_name)=''"))
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as connection:
        if "client_id" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL"))
        if "approval_status" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'APPROVED'"))
        if "approved_at" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN approved_at DATETIME"))
        if "approved_by" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_client_id ON users (client_id) WHERE client_id IS NOT NULL"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_approval_status ON users (approval_status)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_users_approved_by ON users (approved_by)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_clients_email ON clients (email)"))
    inspector = inspect(engine)
    if "customer_orders" in inspector.get_table_names():
        order_columns = {column["name"] for column in inspector.get_columns("customer_orders")}
        additions = {
            "user_id":"INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "approved_at":"DATETIME", "approved_by":"INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "rejected_at":"DATETIME", "rejected_by":"INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "rejection_reason":"TEXT", "purchase_comment":"TEXT",
        }
        with engine.begin() as connection:
            for name, sql_type in additions.items():
                if name not in order_columns: connection.execute(text(f"ALTER TABLE customer_orders ADD COLUMN {name} {sql_type}"))
            for name in ("user_id", "approved_by", "rejected_by"):
                connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_customer_orders_{name} ON customer_orders ({name})"))
    inspector = inspect(engine)
    with engine.begin() as connection:
        if "purchases" in inspector.get_table_names():
            columns={column["name"] for column in inspector.get_columns("purchases")}
            additions={"supplier_id":"INTEGER REFERENCES suppliers(id) ON DELETE RESTRICT","purchase_date":"DATETIME","expected_delivery_date":"DATETIME","supplier_confirmed_delivery_date":"DATETIME","actual_reception_date":"DATETIME","supplier_confirmation_reference":"VARCHAR(100)","supplier_confirmation_contact":"VARCHAR(150)","supplier_confirmation_comment":"TEXT","supplier_accepted_at":"DATETIME","supplier_acceptance_comment":"TEXT","supplier_acceptance_reference":"VARCHAR(100)","supplier_accepted_by":"INTEGER REFERENCES users(id) ON DELETE SET NULL","received_at":"DATETIME","reception_comment":"TEXT","subtotal":"NUMERIC(14,2) NOT NULL DEFAULT 0","tax_amount":"NUMERIC(14,2) NOT NULL DEFAULT 0","created_by":"INTEGER REFERENCES users(id) ON DELETE SET NULL","received_by":"INTEGER REFERENCES users(id) ON DELETE SET NULL"}
            for name,sql_type in additions.items():
                if name not in columns:connection.execute(text(f"ALTER TABLE purchases ADD COLUMN {name} {sql_type}"))
            connection.execute(text("UPDATE purchases SET purchase_date=created_at WHERE purchase_date IS NULL"));connection.execute(text("UPDATE purchases SET subtotal=total WHERE subtotal=0"));connection.execute(text("UPDATE purchases SET supplier_confirmed_delivery_date=expected_delivery_date WHERE supplier_confirmed_delivery_date IS NULL AND expected_delivery_date IS NOT NULL"));connection.execute(text("UPDATE purchases SET actual_reception_date=received_at WHERE actual_reception_date IS NULL AND received_at IS NOT NULL"));connection.execute(text("UPDATE purchases SET supplier_accepted_at=supplier_confirmed_delivery_date WHERE supplier_accepted_at IS NULL AND supplier_confirmed_delivery_date IS NOT NULL"));connection.execute(text("""UPDATE purchases SET status=CASE status WHEN 'draft' THEN 'EN_PREPARATION' WHEN 'ordered' THEN 'COMMANDE_ENVOYEE' WHEN 'supplier_accepted' THEN 'CONFIRMEE_PAR_FOURNISSEUR' WHEN 'supplier_confirmed' THEN 'CONFIRMEE_PAR_FOURNISSEUR' WHEN 'awaiting_receipt' THEN 'CONFIRMEE_PAR_FOURNISSEUR' WHEN 'partially_received' THEN 'CONFIRMEE_PAR_FOURNISSEUR' WHEN 'received' THEN 'RECEPTIONNEE' WHEN 'cancelled' THEN 'ANNULEE' ELSE status END"""));connection.execute(text("CREATE INDEX IF NOT EXISTS ix_purchases_supplier_id ON purchases (supplier_id)"));connection.execute(text("CREATE INDEX IF NOT EXISTS ix_purchases_supplier_accepted_at ON purchases (supplier_accepted_at)"));connection.execute(text("CREATE INDEX IF NOT EXISTS ix_purchases_supplier_accepted_by ON purchases (supplier_accepted_by)"));connection.execute(text("CREATE INDEX IF NOT EXISTS ix_purchases_supplier_confirmed_delivery_date ON purchases (supplier_confirmed_delivery_date)"));connection.execute(text("CREATE INDEX IF NOT EXISTS ix_purchases_actual_reception_date ON purchases (actual_reception_date)"))
        if "purchase_lines" in inspector.get_table_names():
            columns={column["name"] for column in inspector.get_columns("purchase_lines")}
            for name,sql_type in {"received_quantity":"INTEGER NOT NULL DEFAULT 0","discount":"NUMERIC(5,2) NOT NULL DEFAULT 0","tax_rate":"NUMERIC(5,2) NOT NULL DEFAULT 0","tax_amount":"NUMERIC(14,2) NOT NULL DEFAULT 0","total_amount":"NUMERIC(14,2) NOT NULL DEFAULT 0"}.items():
                if name not in columns:connection.execute(text(f"ALTER TABLE purchase_lines ADD COLUMN {name} {sql_type}"))
            connection.execute(text("UPDATE purchase_lines SET tax_amount=line_total*tax_rate/100 WHERE tax_amount=0 AND tax_rate>0"))
            connection.execute(text("UPDATE purchase_lines SET total_amount=line_total+tax_amount WHERE total_amount=0"))
        if "stock_movements" in inspector.get_table_names():
            columns={column["name"] for column in inspector.get_columns("stock_movements")}
            for name,sql_type in {"previous_stock":"INTEGER","new_stock":"INTEGER","reference_type":"VARCHAR(40)","reference_id":"INTEGER","comment":"TEXT","movement_type":"VARCHAR(40)"}.items():
                if name not in columns:connection.execute(text(f"ALTER TABLE stock_movements ADD COLUMN {name} {sql_type}"))
            connection.execute(text("""UPDATE stock_movements SET movement_type = CASE
                WHEN reference_type = 'purchase' THEN 'ENTREE_ACHAT'
                WHEN reference_type = 'customer_order' THEN 'SORTIE_COMMANDE_CLIENT'
                WHEN type = 'IN' THEN 'AJUSTEMENT_POSITIF'
                WHEN type = 'OUT' THEN 'AJUSTEMENT_NEGATIF'
                ELSE 'INVENTAIRE' END WHERE movement_type IS NULL"""))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_stock_movements_movement_type ON stock_movements (movement_type)"))


def backfill_client_accounts(db: Session) -> int:
    """Associe sans doublon les anciens comptes Client et synchronise nom/email."""
    from app.models.entities import ApprovalStatus, Client, Role, User
    changed = 0
    users = list(db.scalars(select(User).where(User.role == Role.CLIENT)))
    for user in users:
        client = user.client
        if not client:
            client = db.scalar(select(Client).where(func.lower(Client.email) == user.email.lower()).order_by(Client.id))
        if not client:
            client = Client(name=user.full_name, email=user.email.lower(), status="active")
            db.add(client); db.flush()
        if user.client_id != client.id or client.name != user.full_name or client.email != user.email.lower():
            user.client = client; client.name = user.full_name; client.email = user.email.lower(); changed += 1
        if user.approval_status is None:
            user.approval_status = ApprovalStatus.APPROVED; changed += 1
    if changed: db.commit()
    return changed
