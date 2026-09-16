"""Indexe les emails clients pour l'association automatique sans doublon."""
from alembic import op
revision = "20260727_02"
down_revision = "20260727_01"
branch_labels = None
depends_on = None
def upgrade():
    op.execute("CREATE INDEX IF NOT EXISTS ix_clients_email ON clients (email)")
def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_clients_email")
