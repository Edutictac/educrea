"""Initial users, sessions and projects."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("email", sa.String(320), nullable=False),
                    sa.Column("password_hash", sa.String(255), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("csrf_hash", sa.String(64), nullable=False),
                    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table("projects", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("slug", sa.String(80), nullable=False),
                    sa.Column("title", sa.String(160), nullable=False),
                    sa.Column("description", sa.Text(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint("owner_id", "slug"))
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])


def downgrade() -> None:
    op.drop_table("projects")
    op.drop_table("sessions")
    op.drop_table("users")

