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
