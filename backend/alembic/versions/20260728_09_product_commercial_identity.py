"""Identité commerciale optionnelle des produits, sans suppression de colonnes historiques."""
from alembic import op
import sqlalchemy as sa
revision="20260728_09";down_revision="20260728_08";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("products",sa.Column("commercial_name",sa.String(180),nullable=True))
    op.add_column("products",sa.Column("active_ingredient",sa.String(180),nullable=True))
    op.create_index("ix_products_commercial_name","products",["commercial_name"]);op.create_index("ix_products_active_ingredient","products",["active_ingredient"])
    op.execute("UPDATE products SET commercial_name=name WHERE commercial_name IS NULL")
def downgrade():
    op.drop_index("ix_products_active_ingredient",table_name="products");op.drop_index("ix_products_commercial_name",table_name="products");op.drop_column("products","active_ingredient");op.drop_column("products","commercial_name")
