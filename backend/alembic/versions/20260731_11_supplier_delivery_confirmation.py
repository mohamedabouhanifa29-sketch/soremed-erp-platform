"""Confirmation de livraison communiquée par le fournisseur."""
from alembic import op
import sqlalchemy as sa
revision="20260731_11";down_revision="20260731_10";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("purchases",sa.Column("supplier_confirmed_delivery_date",sa.DateTime(timezone=True)))
    op.add_column("purchases",sa.Column("actual_reception_date",sa.DateTime(timezone=True)))
    op.add_column("purchases",sa.Column("supplier_confirmation_reference",sa.String(100)))
    op.add_column("purchases",sa.Column("supplier_confirmation_contact",sa.String(150)))
    op.add_column("purchases",sa.Column("supplier_confirmation_comment",sa.Text()))
    op.create_index("ix_purchases_supplier_confirmed_delivery_date","purchases",["supplier_confirmed_delivery_date"]);op.create_index("ix_purchases_actual_reception_date","purchases",["actual_reception_date"])
    op.execute("UPDATE purchases SET supplier_confirmed_delivery_date=expected_delivery_date WHERE expected_delivery_date IS NOT NULL")
    op.execute("UPDATE purchases SET actual_reception_date=received_at WHERE received_at IS NOT NULL")
def downgrade():
    op.drop_index("ix_purchases_actual_reception_date",table_name="purchases");op.drop_index("ix_purchases_supplier_confirmed_delivery_date",table_name="purchases");op.drop_column("purchases","supplier_confirmation_comment");op.drop_column("purchases","supplier_confirmation_contact");op.drop_column("purchases","supplier_confirmation_reference");op.drop_column("purchases","actual_reception_date");op.drop_column("purchases","supplier_confirmed_delivery_date")
