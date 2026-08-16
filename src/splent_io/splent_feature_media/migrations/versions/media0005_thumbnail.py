"""Media thumbnails: a small web-sized copy for gallery grids.

Adds media_item.thumbnail (the thumbnail filename under uploads/thumbs/). Old
rows keep it empty and fall back to the original until backfilled.

Revision ID: media0005_thumbnail
Revises: media0004_gallery
"""

import sqlalchemy as sa
from alembic import op

revision = "media0005_thumbnail"
down_revision = "media0004_gallery"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("media_item", sa.Column("thumbnail", sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column("media_item", "thumbnail")
