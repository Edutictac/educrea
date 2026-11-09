"""Editable video request limits. NULL retains the server defaults."""
from alembic import op
import sqlalchemy as sa

revision = "0022_video_limits"
down_revision = "0021_included_ai_limits"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("included_ai_limits", sa.Column("videos_daily_limit", sa.Integer(), nullable=True))
    op.add_column("included_ai_limits", sa.Column("videos_global_daily_limit", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("included_ai_limits", "videos_global_daily_limit")
    op.drop_column("included_ai_limits", "videos_daily_limit")
