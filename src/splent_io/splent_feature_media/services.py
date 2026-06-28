import os
from datetime import datetime

from flask import current_app
from werkzeug.utils import secure_filename

from splent_io.splent_feature_media.models import MediaItem
from splent_io.splent_feature_media.repositories import MediaRepository
from splent_framework.db import db
from splent_framework.services.BaseService import BaseService


class MediaService(BaseService):
    def __init__(self):
        super().__init__(MediaRepository())

    def list_recent(self):
        return self.repository.list_recent()

    def _upload_dir(self) -> str:
        d = os.path.join(current_app.static_folder, "uploads")
        os.makedirs(d, exist_ok=True)
        return d

    def save_upload(self, file_storage, title: str = "", alt: str = ""):
        """Persist an uploaded file to the product's static/uploads/ and record it."""
        filename = secure_filename(file_storage.filename or "")
        if not filename:
            return None

        upload_dir = self._upload_dir()
        base, ext = os.path.splitext(filename)
        candidate, i = filename, 1
        while os.path.exists(os.path.join(upload_dir, candidate)):
            i += 1
            candidate = f"{base}-{i}{ext}"

        path = os.path.join(upload_dir, candidate)
        file_storage.save(path)

        item = MediaItem(
            filename=candidate,
            url=f"/static/uploads/{candidate}",
            alt=alt,
            title=title or base,
            mime_type=file_storage.mimetype or "",
            size=os.path.getsize(path),
            uploaded_at=datetime.utcnow(),
        )
        db.session.add(item)
        db.session.commit()
        return item

    def import_from_url(self, url: str, title: str = "", alt: str = ""):
        """Download an external image into the media library and record it.

        Idempotent by ``source_url``: importing the same URL twice returns the
        existing item. Used to pull remote images (team photos, post thumbnails…)
        into the local library so they are served from the product, not a 3rd
        party — the WordPress "Media Library" behaviour.
        """
        if not url:
            return None
        existing = MediaItem.query.filter_by(source_url=url).first()
        if existing:
            return existing

        import requests
        from urllib.parse import urlparse

        try:
            resp = requests.get(url, timeout=25)
            resp.raise_for_status()
        except Exception:
            return None

        name = os.path.basename(urlparse(url).path) or "image"
        filename = secure_filename(name)
        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        if not os.path.splitext(filename)[1]:
            ext = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "image/svg+xml": ".svg",
            }.get(content_type, "")
            filename = f"{filename or 'image'}{ext}"

        upload_dir = self._upload_dir()
        base, ext = os.path.splitext(filename)
        candidate, i = filename, 1
        while os.path.exists(os.path.join(upload_dir, candidate)):
            i += 1
            candidate = f"{base}-{i}{ext}"

        path = os.path.join(upload_dir, candidate)
        with open(path, "wb") as f:
            f.write(resp.content)

        item = MediaItem(
            filename=candidate,
            url=f"/static/uploads/{candidate}",
            source_url=url,
            alt=alt,
            title=title or base,
            mime_type=content_type or "image/jpeg",
            size=len(resp.content),
            uploaded_at=datetime.utcnow(),
        )
        db.session.add(item)
        db.session.commit()
        return item

    def delete_item(self, item_id: int) -> bool:
        item = self.repository.get_by_id(item_id)
        if not item:
            return False
        try:
            path = os.path.join(current_app.static_folder, "uploads", item.filename)
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        db.session.delete(item)
        db.session.commit()
        return True
