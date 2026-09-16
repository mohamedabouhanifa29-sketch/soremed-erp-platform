"""Ajoute l'historique privé de l'assistant local."""
from alembic import op
import sqlalchemy as sa
revision="20260728_06";down_revision="20260728_05";branch_labels=None;depends_on=None
def upgrade():
    op.create_table("chat_messages",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.String(20),nullable=False),sa.Column("message",sa.Text(),nullable=False),sa.Column("response",sa.Text(),nullable=False),sa.Column("intent",sa.String(60),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_chat_messages_user_id","chat_messages",["user_id"]);op.create_index("ix_chat_messages_created_at","chat_messages",["created_at"])
def downgrade():op.drop_table("chat_messages")
