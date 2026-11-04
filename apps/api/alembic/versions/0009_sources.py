"""Reference sources (curriculum documents) and proposal grounding."""

from alembic import op
import sqlalchemy as sa

revision = "0009_sources"
down_revision = "0008_oidc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sources_project_id", "sources", ["project_id"])
    op.create_table("source_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(300), nullable=False, server_default=""),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False))
    op.create_index("ix_source_chunks_source_id", "source_chunks", ["source_id"])
    op.create_index("ix_source_chunks_project_id", "source_chunks", ["project_id"])
    op.add_column("ai_proposals", sa.Column("grounding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_proposals", "grounding")
    op.drop_index("ix_source_chunks_project_id", table_name="source_chunks")
    op.drop_index("ix_source_chunks_source_id", table_name="source_chunks")
    op.drop_table("source_chunks")
    op.drop_index("ix_sources_project_id", table_name="sources")
    op.drop_table("sources")
