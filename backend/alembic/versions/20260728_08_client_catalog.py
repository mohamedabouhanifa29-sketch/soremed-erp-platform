"""Métadonnées produit optionnelles et favoris clients."""
from alembic import op
import sqlalchemy as sa
revision="20260728_08";down_revision="20260728_07";branch_labels=None;depends_on=None
def upgrade():
    for name,size in (("laboratory",160),("dosage",100),("pharmaceutical_form",100),("packaging",160)):
        op.add_column("products",sa.Column(name,sa.String(size),nullable=True))
    op.create_table("favorites",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("product_id",sa.Integer(),sa.ForeignKey("products.id",ondelete="CASCADE"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("user_id","product_id",name="uq_favorite_user_product"))
    op.create_index("ix_favorites_user_id","favorites",["user_id"]);op.create_index("ix_favorites_product_id","favorites",["product_id"])
def downgrade():
    op.drop_table("favorites")
    for name in ("packaging","pharmaceutical_form","dosage","laboratory"):op.drop_column("products",name)
