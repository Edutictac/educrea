"""Encrypted personal credentials and reviewable AI proposals."""

from alembic import op
import sqlalchemy as sa

revision = "0003_ai_proposals"
down_revision = "0002_project_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("ai_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("free_confirmations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "provider"))
    op.create_index("ix_ai_credentials_user_id", "ai_credentials", ["user_id"])
    op.create_table("ai_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_ai_proposals_project_id", "ai_proposals", ["project_id"])
    op.create_index("ix_ai_proposals_user_id", "ai_proposals", ["user_id"])


def downgrade() -> None:
    op.drop_table("ai_proposals")
    op.drop_table("ai_credentials")

