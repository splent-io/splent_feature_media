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

    def get(self, item_id: int):
        """Fetch a single MediaItem by id (or None)."""
        return self.repository.get_by_id(item_id)

    def update_meta(self, item, alt: str = "", title: str = ""):
        """Update the editable metadata (alt text + title) of a media item."""
        if item is None:
            return None
        item.alt = alt or ""
        item.title = title or ""
        db.session.commit()
        return item

    def _abs_path(self, item) -> str:
        """Absolute path to the item's file inside static/uploads/."""
        return os.path.join(current_app.static_folder, "uploads", item.filename)

    def dimensions(self, item):
        """Return (width, height) in pixels for an image item, else None.

        Uses Pillow and is defensive: any failure (missing file, non-image,
        unreadable) returns None so the detail page still renders.
        """
        if item is None or not item.is_image:
            return None
        try:
            from PIL import Image

            with Image.open(self._abs_path(item)) as im:
                return im.size  # (width, height)
        except Exception:
            return None

    def save_cropped(self, item, file_storage):
        """Persist an already-cropped image (from the client) as a NEW MediaItem.

        The crop + rotation geometry is performed entirely on the client by
        Cropper.js (``getCroppedCanvas()``), which is the single source of
        truth: the browser ships the finished pixels. Here we only validate the
        bytes with Pillow, normalise to a safe format, and save it alongside the
        original (the original file and record are preserved). ``file_storage``
        is the uploaded werkzeug FileStorage. Returns the new MediaItem, or None
        if the item is not an image or the upload is not a decodable image.
        """
        if item is None or not item.is_image:
            return None
        if file_storage is None:
            return None

        try:
            from PIL import Image
        except Exception:
            return None

        # Validate + decode the uploaded bytes. A non-image upload is rejected.
        try:
            file_storage.stream.seek(0)
            im = Image.open(file_storage.stream)
            im.load()
        except Exception:
            return None

        # Normalise format/extension from the ORIGINAL so the crop matches it.
        base, ext = os.path.splitext(item.filename)
        ext = ext.lower()
        if ext in (".jpg", ".jpeg"):
            fmt, out_ext = "JPEG", ext
            if im.mode != "RGB":
                im = im.convert("RGB")
        elif ext == ".webp":
            fmt, out_ext = "WEBP", ".webp"
        else:
            fmt, out_ext = "PNG", ".png"
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")

        # Collision-safe filename in the product's static/uploads/.
        upload_dir = self._upload_dir()
        candidate = f"{base}-cropped{out_ext}"
        i = 1
        while os.path.exists(os.path.join(upload_dir, candidate)):
            i += 1
            candidate = f"{base}-cropped-{i}{out_ext}"

        out_path = os.path.join(upload_dir, candidate)
        try:
            im.save(out_path, fmt)
        except Exception:
            return None

        mime = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }.get(fmt, "image/png")

        new_item = MediaItem(
            filename=candidate,
            url=f"/static/uploads/{candidate}",
            source_url=item.source_url or "",
            alt=item.alt or "",
            title=f"{item.title or item.filename} (cropped)",
            mime_type=mime,
            size=os.path.getsize(out_path),
            uploaded_at=datetime.utcnow(),
        )
        db.session.add(new_item)
        db.session.commit()
        return new_item

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
