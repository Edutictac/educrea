"""Project video library: generated or uploaded MP4 files kept apart from image assets."""
from alembic import op
import sqlalchemy as sa

revision = "0018_project_videos"
down_revision = "0017_open_workspace"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_videos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(160), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("credit", sa.String(300), nullable=False, server_default=""),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution", sa.String(10), nullable=False, server_default=""),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path", name="uq_project_videos_project_path"),
    )
    op.create_index("ix_project_videos_project_id", "project_videos", ["project_id"])


def downgrade():
    op.drop_index("ix_project_videos_project_id", table_name="project_videos")
    op.drop_table("project_videos")
