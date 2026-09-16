"""Sépare les achats fournisseurs et enrichit leur réception et leurs mouvements."""
from alembic import op
import sqlalchemy as sa
revision="20260728_05"
down_revision="20260728_04"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("suppliers",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("name",sa.String(150),nullable=False),sa.Column("company_name",sa.String(180)),sa.Column("ice",sa.String(30),unique=True),sa.Column("rc",sa.String(30)),sa.Column("email",sa.String(255)),sa.Column("phone",sa.String(30)),sa.Column("address",sa.Text()),sa.Column("city",sa.String(80)),sa.Column("primary_contact",sa.String(150)),sa.Column("status",sa.String(20),nullable=False,server_default="active"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    with op.batch_alter_table("purchases") as b:
        b.add_column(sa.Column("supplier_id",sa.Integer()));b.add_column(sa.Column("purchase_date",sa.DateTime(timezone=True)));b.add_column(sa.Column("expected_delivery_date",sa.DateTime(timezone=True)));b.add_column(sa.Column("received_at",sa.DateTime(timezone=True)));b.add_column(sa.Column("subtotal",sa.Numeric(14,2),server_default="0",nullable=False));b.add_column(sa.Column("tax_amount",sa.Numeric(14,2),server_default="0",nullable=False));b.add_column(sa.Column("created_by",sa.Integer()));b.add_column(sa.Column("received_by",sa.Integer()));b.create_foreign_key("fk_purchase_supplier","suppliers",["supplier_id"],["id"],ondelete="RESTRICT")
    with op.batch_alter_table("purchase_lines") as b:
        b.add_column(sa.Column("received_quantity",sa.Integer(),server_default="0",nullable=False));b.add_column(sa.Column("discount",sa.Numeric(5,2),server_default="0",nullable=False));b.add_column(sa.Column("tax_rate",sa.Numeric(5,2),server_default="0",nullable=False))
    with op.batch_alter_table("stock_movements") as b:
        b.add_column(sa.Column("previous_stock",sa.Integer()));b.add_column(sa.Column("new_stock",sa.Integer()));b.add_column(sa.Column("reference_type",sa.String(40)));b.add_column(sa.Column("reference_id",sa.Integer()));b.add_column(sa.Column("comment",sa.Text()))

def downgrade():
    with op.batch_alter_table("stock_movements") as b:
        for c in ("comment","reference_id","reference_type","new_stock","previous_stock"):b.drop_column(c)
    with op.batch_alter_table("purchase_lines") as b:
        for c in ("tax_rate","discount","received_quantity"):b.drop_column(c)
    with op.batch_alter_table("purchases") as b:
        for c in ("received_by","created_by","tax_amount","subtotal","received_at","expected_delivery_date","purchase_date","supplier_id"):b.drop_column(c)
    op.drop_table("suppliers")
