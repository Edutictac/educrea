"""Account-bound beta waitlist; applying never grants institutional AI permission."""
from alembic import op
import sqlalchemy as sa

revision = "0015_included_ai_waitlist"
down_revision = "0014_included_ai_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("included_ai_waitlist",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("teaching_context", sa.Text(), nullable=False),
        sa.Column("intended_use", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_included_ai_waitlist_status", "included_ai_waitlist", ["status"])


def downgrade():
    op.drop_index("ix_included_ai_waitlist_status", table_name="included_ai_waitlist")
    op.drop_table("included_ai_waitlist")
