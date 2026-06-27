from datetime import datetime

from splent_framework.db import db


class MediaItem(db.Model):
    """A file in the media library (the analogue of WordPress' Media Library)."""

    __tablename__ = "media_item"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(512), nullable=False)
    url = db.Column(db.String(512), nullable=False)  # /static/uploads/<filename>
    alt = db.Column(db.String(255), default="")
    title = db.Column(db.String(255), default="")
    mime_type = db.Column(db.String(128), default="")
    size = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_image(self):
        return (self.mime_type or "").startswith("image/")

    def __repr__(self):
        return f"MediaItem<{self.id}:{self.filename}>"
