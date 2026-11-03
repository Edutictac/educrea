"""Per-path file history."""

from alembic import op
import sqlalchemy as sa

revision = "0006_file_versions"
down_revision = "0005_paid_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("file_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(10), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path", "version"))
    op.create_index("ix_file_versions_project_id", "file_versions", ["project_id"])
    # Seed the current content of existing files so history starts from today's state.
    op.execute("INSERT INTO file_versions (id, project_id, path, version, content, source, created_at) "
               "SELECT id, project_id, path, version, content, 'manual', updated_at FROM project_files")


def downgrade() -> None:
    op.drop_index("ix_file_versions_project_id", table_name="file_versions")
    op.drop_table("file_versions")
