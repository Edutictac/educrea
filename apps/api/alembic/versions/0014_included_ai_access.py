"""Opt-in beta access per account. No automatic grants for existing or new users."""
from alembic import op
import sqlalchemy as sa

revision = "0014_included_ai_access"
down_revision = "0013_included_ai"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("included_ai_access",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_table("included_ai_access")
