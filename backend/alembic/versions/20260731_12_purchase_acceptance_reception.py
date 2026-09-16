"""Acceptation fournisseur et réception cumulative non destructives."""
from alembic import op
import sqlalchemy as sa

revision = "20260731_12"
down_revision = "20260731_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("purchases") as batch:
        batch.add_column(sa.Column("supplier_accepted_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("supplier_acceptance_comment", sa.Text()))
        batch.add_column(sa.Column("supplier_acceptance_reference", sa.String(100)))
        batch.add_column(sa.Column("supplier_accepted_by", sa.Integer()))
        batch.add_column(sa.Column("reception_comment", sa.Text()))
        batch.create_foreign_key("fk_purchase_supplier_accepted_by", "users", ["supplier_accepted_by"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_purchases_supplier_accepted_at", ["supplier_accepted_at"])
        batch.create_index("ix_purchases_supplier_accepted_by", ["supplier_accepted_by"])
    op.execute("UPDATE purchases SET supplier_accepted_at=supplier_confirmed_delivery_date WHERE supplier_confirmed_delivery_date IS NOT NULL")
    op.execute("UPDATE purchases SET status='supplier_accepted' WHERE status IN ('supplier_confirmed','awaiting_receipt')")


def downgrade() -> None:
    with op.batch_alter_table("purchases") as batch:
        batch.drop_index("ix_purchases_supplier_accepted_by")
        batch.drop_index("ix_purchases_supplier_accepted_at")
        batch.drop_constraint("fk_purchase_supplier_accepted_by", type_="foreignkey")
        for name in ("reception_comment", "supplier_accepted_by", "supplier_acceptance_reference", "supplier_acceptance_comment", "supplier_accepted_at"):
            batch.drop_column(name)
