"""Add in_gallery to media_item: the public gallery is a curated subset.

Existing images stay in the gallery (server default 1) except the files that
features bundled through their seeders (source_url "seed://…": logos,
posters, portraits), which were never gallery photos and are switched off.

Revision ID: media0004_gallery
Revises: media0003_protected
"""

import sqlalchemy as sa
from alembic import op

revision = "media0004_gallery"
down_revision = "media0003_protected"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "media_item",
        sa.Column("in_gallery", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_media_item_in_gallery", "media_item", ["in_gallery"])
    op.execute("UPDATE media_item SET in_gallery = 0 WHERE source_url LIKE 'seed://%'")
    op.execute("UPDATE media_item SET in_gallery = 0 WHERE mime_type NOT LIKE 'image/%'")


def downgrade():
    op.drop_index("ix_media_item_in_gallery", table_name="media_item")
    op.drop_column("media_item", "in_gallery")
