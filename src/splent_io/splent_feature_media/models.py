from datetime import datetime

from splent_framework.db import db


class MediaItem(db.Model):
    """A file in the media library (the analogue of WordPress' Media Library)."""

    __tablename__ = "media_item"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(512), nullable=False)
    url = db.Column(db.String(512), nullable=False)  # /static/uploads/<filename>
    # A small web-sized copy under /static/uploads/thumbs/, used in grids so a
    # gallery never downloads full-resolution originals as thumbnails. Empty
    # for non-images and for items whose thumbnail has not been generated yet
    # (thumbnail_url then falls back to the original).
    thumbnail = db.Column(db.String(512), default="")
    source_url = db.Column(db.String(1024), default="")  # original URL when imported
    alt = db.Column(db.String(255), default="")
    title = db.Column(db.String(255), default="")
    mime_type = db.Column(db.String(128), default="")
    size = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    # "public" files live in static/uploads and are served by the web server.
    # "restricted" files live outside static/ and are only served through
    # /media/file/<id> after the owning feature's access resolver allows it
    # (deny by default, see splent_framework.services.file_access).
    access = db.Column(
        db.String(16), default="public", server_default="public", nullable=False
    )
    owner_feature = db.Column(db.String(64), nullable=True)
    owner_ref = db.Column(db.String(255), nullable=True)
    # Whether the item belongs in the public gallery (/media and the
    # homepage strip). The library holds every file a site needs, logos and
    # posters and portraits included; the gallery is the curated subset an
    # editor wants visitors to browse. Files bundled by features (seeds) and
    # imported illustrations start outside it; uploads and photo imports
    # start inside it, and the admin toggles any item either way.
    in_gallery = db.Column(
        db.Boolean, default=True, server_default="1", nullable=False, index=True
    )

    @property
    def is_image(self):
        return (self.mime_type or "").startswith("image/")

    @property
    def is_public(self):
        return self.access == "public"

    @property
    def thumbnail_url(self):
        """A grid-sized image: the generated thumbnail when present, else the
        original. Callers use this for <img src> in galleries and keep `url`
        for the full-size lightbox."""
        if self.thumbnail and self.is_public:
            return f"/static/uploads/thumbs/{self.thumbnail}"
        return self.url

    def __repr__(self):
        return f"MediaItem<{self.id}:{self.filename}>"
