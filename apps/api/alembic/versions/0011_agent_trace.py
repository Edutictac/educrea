"""AI proposals keep the trace of the capabilities the agent consulted (names, status, never the results)."""

from alembic import op
import sqlalchemy as sa

revision = "0011_agent_trace"
down_revision = "0010_source_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_proposals", sa.Column("agent_trace", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_proposals", "agent_trace")
