"""Image library: PNG/JPEG uploaded by the teacher, with required alternative text and credit."""

from alembic import op
import sqlalchemy as sa

revision = "0012_project_assets"
down_revision = "0011_agent_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(120), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("alt", sa.String(300), nullable=False),
        sa.Column("credit", sa.String(300), nullable=False, server_default=""),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path"),
    )
    op.create_index("ix_project_assets_project_id", "project_assets", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_assets_project_id", table_name="project_assets")
    op.drop_table("project_assets")
