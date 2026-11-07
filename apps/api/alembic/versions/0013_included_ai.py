"""Institutional credits in the existing usage ledger; personal keys remain untouched."""
from alembic import op
import sqlalchemy as sa

revision = "0013_included_ai"
down_revision = "0012_project_assets"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("period_key", sa.String(7), nullable=True),
        sa.Column("reserved_credits", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("actual_credits", sa.BigInteger(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("credits_per_usd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minimum_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_type", sa.String(60), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("ai_usage", column)
    op.create_index("ix_ai_usage_user_period_mode", "ai_usage", ["user_id", "period_key", "mode"])
    op.create_index("ix_ai_usage_request_id", "ai_usage", ["request_id"])
    op.create_table("ai_budget_alerts",
        sa.Column("period_key", sa.String(7), primary_key=True),
        sa.Column("threshold", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("ai_budget_alerts")
    op.drop_index("ix_ai_usage_request_id", table_name="ai_usage")
    op.drop_index("ix_ai_usage_user_period_mode", table_name="ai_usage")
    for column in ("finished_at", "latency_ms", "task_type", "minimum_credits", "credits_per_usd",
                   "output_tokens", "input_tokens", "actual_credits", "reserved_credits", "period_key", "request_id"):
        op.drop_column("ai_usage", column)
