"""Personal monthly budgets and paid usage accounting."""

from alembic import op
import sqlalchemy as sa

revision = "0005_paid_budgets"
down_revision = "0004_ai_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_usage", sa.Column("mode", sa.String(10), nullable=False, server_default="free"))
    op.add_column("ai_usage", sa.Column("reserved_cost_microusd", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_usage", sa.Column("actual_cost_microusd", sa.Integer(), nullable=True))
    op.add_column("ai_usage", sa.Column("input_rate_microusd", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_usage", sa.Column("output_rate_microusd", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("ai_budgets",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("monthly_limit_microusd", sa.Integer(), nullable=False))


def downgrade() -> None:
    op.drop_table("ai_budgets")
    op.drop_column("ai_usage", "output_rate_microusd")
    op.drop_column("ai_usage", "input_rate_microusd")
    op.drop_column("ai_usage", "actual_cost_microusd")
    op.drop_column("ai_usage", "reserved_cost_microusd")
    op.drop_column("ai_usage", "mode")
