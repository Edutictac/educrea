"""Administrator overrides for institutional image quotas. Downgrade restores environment values."""
from alembic import op
import sqlalchemy as sa

revision = "0021_included_ai_limits"
down_revision = "0020_test_billing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "included_ai_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("images_weekly_limit", sa.Integer(), nullable=True),
        sa.Column("images_global_daily_limit", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("included_ai_limits")
