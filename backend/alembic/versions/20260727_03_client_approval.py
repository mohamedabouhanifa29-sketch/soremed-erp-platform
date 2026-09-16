"""Ajoute le cycle d'approbation des inscriptions Client."""
from alembic import op
import sqlalchemy as sa
revision = "20260727_03"
down_revision = "20260727_02"
branch_labels = None
depends_on = None
def upgrade():
    approval=sa.Enum("PENDING","APPROVED","REJECTED",name="approvalstatus")
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("approval_status",approval,nullable=False,server_default="APPROVED"))
        batch.add_column(sa.Column("approved_at",sa.DateTime(timezone=True),nullable=True))
        batch.add_column(sa.Column("approved_by",sa.Integer(),nullable=True))
        batch.create_foreign_key("fk_users_approved_by","users",["approved_by"],["id"],ondelete="SET NULL")
        batch.create_index("ix_users_approval_status",["approval_status"])
        batch.create_index("ix_users_approved_by",["approved_by"])
def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("approved_by");batch.drop_column("approved_at");batch.drop_column("approval_status")
