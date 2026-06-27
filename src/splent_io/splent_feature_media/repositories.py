from __future__ import annotations

from splent_io.splent_feature_media.models import MediaItem
from splent_framework.repositories.BaseRepository import BaseRepository


class MediaRepository(BaseRepository):
    def __init__(self):
        super().__init__(MediaItem)

    def list_recent(self) -> list[MediaItem]:
        return MediaItem.query.order_by(MediaItem.uploaded_at.desc()).all()
