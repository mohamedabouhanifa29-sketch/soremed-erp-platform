"""Ajoute le workflow de validation des commandes clients sans supprimer les données."""
from alembic import op
import sqlalchemy as sa

revision = "20260728_04"
down_revision = "20260727_03"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("customer_orders") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rejected_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("purchase_comment", sa.Text(), nullable=True))
        batch.create_foreign_key("fk_customer_orders_user", "users", ["user_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_customer_orders_approved_by", "users", ["approved_by"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_customer_orders_rejected_by", "users", ["rejected_by"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_customer_orders_user_id", ["user_id"])
        batch.create_index("ix_customer_orders_approved_by", ["approved_by"])
        batch.create_index("ix_customer_orders_rejected_by", ["rejected_by"])

def downgrade():
    with op.batch_alter_table("customer_orders") as batch:
        for name in ("purchase_comment", "rejection_reason", "rejected_by", "rejected_at", "approved_by", "approved_at", "user_id"):
            batch.drop_column(name)
