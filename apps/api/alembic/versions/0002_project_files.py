"""Persist editable project files with optimistic versions."""

from alembic import op
import sqlalchemy as sa

revision = "0002_project_files"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path"),
    )
    op.create_index("ix_project_files_project_id", "project_files", ["project_id"])


def downgrade() -> None:
    op.drop_table("project_files")

