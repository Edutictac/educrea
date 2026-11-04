"""OpenID Connect identities and login flows."""

from alembic import op
import sqlalchemy as sa

revision = "0008_oidc"
down_revision = "0007_capability_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("oidc_identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer", sa.String(300), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject"))
    op.create_index("ix_oidc_identities_user_id", "oidc_identities", ["user_id"])
    op.create_table("oidc_flows",
        sa.Column("cookie_hash", sa.String(64), primary_key=True),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("verifier", sa.String(128), nullable=False),
        sa.Column("next_path", sa.String(300), nullable=False, server_default="/projects"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("oidc_flows")
    op.drop_index("ix_oidc_identities_user_id", table_name="oidc_identities")
    op.drop_table("oidc_identities")
