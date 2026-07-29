"""Add access control columns to media_item (protected file serving).

Every pre-existing row keeps access="public" via the server default, so
nothing changes for current products. Restricted items record the feature
that owns them (owner_feature + owner_ref) so the framework's file access
registry can ask that feature before serving.

Revision ID: media0003_protected
Revises: media0002_source_url
"""

import sqlalchemy as sa
from alembic import op

revision = "media0003_protected"
down_revision = "media0002_source_url"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "media_item",
        sa.Column(
            "access", sa.String(length=16), nullable=False, server_default="public"
        ),
    )
    op.add_column(
        "media_item", sa.Column("owner_feature", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "media_item", sa.Column("owner_ref", sa.String(length=255), nullable=True)
    )


def downgrade():
    op.drop_column("media_item", "owner_ref")
    op.drop_column("media_item", "owner_feature")
    op.drop_column("media_item", "access")
