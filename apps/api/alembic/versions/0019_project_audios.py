"""Project audio library, including reviewed transcripts or listening descriptions."""
from alembic import op
import sqlalchemy as sa

revision = "0019_project_audios"
down_revision = "0018_project_videos"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_audios",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(160), nullable=False),
        sa.Column("media_type", sa.String(30), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("credit", sa.String(300), nullable=False, server_default=""),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path", name="uq_project_audios_project_path"),
    )
    op.create_index("ix_project_audios_project_id", "project_audios", ["project_id"])


def downgrade():
    op.drop_index("ix_project_audios_project_id", table_name="project_audios")
    op.drop_table("project_audios")
