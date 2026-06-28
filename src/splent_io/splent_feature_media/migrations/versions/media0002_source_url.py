"""Add source_url to media_item (records the original URL of imported media).

Revision ID: media0002_source_url
Revises: c759746adc2e
"""

import sqlalchemy as sa
from alembic import op

revision = "media0002_source_url"
down_revision = "c759746adc2e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "media_item", sa.Column("source_url", sa.String(length=1024), nullable=True)
    )


def downgrade():
    op.drop_column("media_item", "source_url")
