"""Full anonymous workspaces with isolated sessions; no saved guest API keys."""
from alembic import op
import sqlalchemy as sa

revision = "0017_open_workspace"
down_revision = "0016_beta_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()))
    # SQLite cannot add a foreign key via ALTER TABLE; this optional flow reference is validated by the service.
    op.add_column("oidc_flows", sa.Column("guest_user_id", sa.Uuid(), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_oidc_flow_guest", "oidc_flows", "users", ["guest_user_id"], ["id"], ondelete="SET NULL")


def downgrade():
    op.drop_column("oidc_flows", "guest_user_id")
    op.drop_column("users", "is_guest")
