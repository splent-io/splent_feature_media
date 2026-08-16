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

    def _gallery_query(self):
        """Public images an editor left in the gallery, newest first."""
        return (
            MediaItem.query.filter_by(access="public", in_gallery=True)
            .filter(MediaItem.mime_type.like("image/%"))
            .order_by(MediaItem.uploaded_at.desc(), MediaItem.id.desc())
        )

    def list_public_images(self, limit: int) -> list[MediaItem]:
        """The latest gallery images, at most ``limit``."""
        return self._gallery_query().limit(limit).all()

    def list_gallery(self, page: int, per_page: int) -> list[MediaItem]:
        """One page of the gallery (1-based)."""
        page = max(1, page)
        return self._gallery_query().offset((page - 1) * per_page).limit(per_page).all()

    def count_gallery(self) -> int:
        return self._gallery_query().count()

    def list_all_recent(self) -> list[MediaItem]:
        return MediaItem.query.order_by(MediaItem.uploaded_at.desc()).all()
