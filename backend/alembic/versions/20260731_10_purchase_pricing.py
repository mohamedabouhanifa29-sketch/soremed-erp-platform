"""Tarification d'achat distincte et non destructive."""
from alembic import op
import sqlalchemy as sa
revision="20260731_10";down_revision="20260728_09";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("products",sa.Column("default_purchase_price",sa.Numeric(12,2),nullable=True))
    op.add_column("purchase_lines",sa.Column("tax_amount",sa.Numeric(14,2),nullable=False,server_default="0"))
    op.add_column("purchase_lines",sa.Column("total_amount",sa.Numeric(14,2),nullable=False,server_default="0"))
    op.create_table("supplier_products",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("supplier_id",sa.Integer(),sa.ForeignKey("suppliers.id",ondelete="CASCADE"),nullable=False),sa.Column("product_id",sa.Integer(),sa.ForeignKey("products.id",ondelete="CASCADE"),nullable=False),sa.Column("purchase_price",sa.Numeric(12,2),nullable=False),sa.Column("supplier_reference",sa.String(100)),sa.Column("minimum_order_quantity",sa.Integer(),nullable=False,server_default="1"),sa.Column("last_purchase_date",sa.DateTime(timezone=True)),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("supplier_id","product_id",name="uq_supplier_product"))
    op.create_index("ix_supplier_products_supplier_id","supplier_products",["supplier_id"]);op.create_index("ix_supplier_products_product_id","supplier_products",["product_id"]);op.create_index("ix_supplier_products_is_active","supplier_products",["is_active"])
    op.execute("UPDATE purchase_lines SET tax_amount=line_total*tax_rate/100, total_amount=line_total+(line_total*tax_rate/100)")
def downgrade():
    op.drop_table("supplier_products");op.drop_column("purchase_lines","total_amount");op.drop_column("purchase_lines","tax_amount");op.drop_column("products","default_purchase_price")
