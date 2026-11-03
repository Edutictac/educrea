"""Audit log for typed capability / MCP invocations."""

from alembic import op
import sqlalchemy as sa

revision = "0007_capability_calls"
down_revision = "0006_file_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("capability_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability", sa.String(160), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("detail", sa.String(200), nullable=False, server_default=""),
        sa.Column("input_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_capability_calls_user_id", "capability_calls", ["user_id"])
    op.create_index("ix_capability_calls_project_id", "capability_calls", ["project_id"])
    op.create_index("ix_capability_calls_created_at", "capability_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("capability_calls")
