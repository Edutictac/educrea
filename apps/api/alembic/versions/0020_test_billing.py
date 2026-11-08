"""Sandbox top-ups and append-only credit entries. Downgrade discards test data."""
from alembic import op
import sqlalchemy as sa

revision = "0020_test_billing"
down_revision = "0019_project_audios"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "billing_test_topups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.String(255), unique=True),
        sa.Column("checkout_url", sa.String(2048)),
        sa.Column("return_base", sa.String(500), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "request_id"),
    )
    op.create_table(
        "billing_test_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topup_id", sa.Uuid(), sa.ForeignKey("billing_test_topups.id"), unique=True, nullable=False),
        sa.Column("amount_microeur", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_microeur = 10000000", name="ck_test_topup_amount"),
    )


def downgrade():
    op.drop_table("billing_test_entries")
    op.drop_table("billing_test_topups")
