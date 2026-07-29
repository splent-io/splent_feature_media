from __future__ import annotations

from splent_io.splent_feature_media.models import MediaItem
from splent_framework.repositories.BaseRepository import BaseRepository


class MediaRepository(BaseRepository):
    def __init__(self):
        super().__init__(MediaItem)

    def list_recent(self) -> list[MediaItem]:
        """Public items only.

        This is what the shared picker and every cross-feature consumer sees,
        so a restricted file can never be picked as a public page's image nor
        have its name enumerated. Use list_all_recent() from screens that are
        already gated and legitimately manage protected material.
        """
        return self.list_public_recent()

    def list_public_recent(self) -> list[MediaItem]:
        return (
            MediaItem.query.filter_by(access="public")
            .order_by(MediaItem.uploaded_at.desc())
            .all()
        )

    def list_all_recent(self) -> list[MediaItem]:
        return MediaItem.query.order_by(MediaItem.uploaded_at.desc()).all()
