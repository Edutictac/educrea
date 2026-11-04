"""Sources can come from a public URL."""

from alembic import op
import sqlalchemy as sa

revision = "0010_source_url"
down_revision = "0009_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("url", sa.String(500), nullable=True))
    op.add_column("sources", sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "fetched_at")
    op.drop_column("sources", "url")
