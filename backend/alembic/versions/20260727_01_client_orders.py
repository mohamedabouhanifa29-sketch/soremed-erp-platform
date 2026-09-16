"""Lie les comptes clients et ajoute les commandes catalogue."""
from alembic import op
import sqlalchemy as sa
revision = "20260727_01"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("client_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_users_client_id", "clients", ["client_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_users_client_id", ["client_id"], unique=True)
    status = sa.Enum("PENDING", "CONFIRMED", "PREPARED", "DELIVERED", "CANCELLED", name="orderstatus")
    op.create_table("customer_orders", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("number", sa.String(50), nullable=False), sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False), sa.Column("status", status, nullable=False), sa.Column("total", sa.Numeric(14,2), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_customer_orders_number", "customer_orders", ["number"], unique=True)
    op.create_index("ix_customer_orders_client_id", "customer_orders", ["client_id"])
    op.create_table("customer_order_lines", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("customer_orders.id", ondelete="CASCADE"), nullable=False), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False), sa.Column("product_name", sa.String(160), nullable=False), sa.Column("product_reference", sa.String(60), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("unit_price", sa.Numeric(12,2), nullable=False), sa.Column("line_total", sa.Numeric(14,2), nullable=False), sa.UniqueConstraint("order_id", "product_id", name="uq_customer_order_product"))
def downgrade():
    op.drop_table("customer_order_lines"); op.drop_table("customer_orders")
    with op.batch_alter_table("users") as batch: batch.drop_column("client_id")
