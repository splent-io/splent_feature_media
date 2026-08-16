import mimetypes
import os
import shutil
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
        """Public items only. See MediaRepository.list_recent."""
        return self.repository.list_recent()

    def list_public_recent(self):
        return self.repository.list_public_recent()

    def list_public_images(self, limit: int = 6):
        """The latest gallery images (homepage section, teasers)."""
        return self.repository.list_public_images(limit)

    def gallery_page(self, page: int = 1, per_page: int = 48):
        """One page of the public gallery plus whether more follow."""
        items = self.repository.list_gallery(page, per_page + 1)
        has_more = len(items) > per_page
        return items[:per_page], has_more

    def count_gallery(self) -> int:
        return self.repository.count_gallery()

    def set_in_gallery(self, item, flag: bool):
        """Put an item in the public gallery or take it out."""
        if item is None:
            return None
        item.in_gallery = bool(flag)
        db.session.commit()
        return item

    def list_all_recent(self):
        """Every item including restricted ones. Callers must be gated."""
        return self.repository.list_all_recent()

    def get(self, item_id: int):
        """Fetch a single MediaItem by id (or None)."""
        return self.repository.get_by_id(item_id)

    def update_meta(self, item, alt: str = "", title: str = "", in_gallery=None):
        """Update the editable metadata (alt text, title, gallery flag)."""
        if item is None:
            return None
        item.alt = alt or ""
        item.title = title or ""
        if in_gallery is not None:
            item.in_gallery = bool(in_gallery)
        db.session.commit()
        return item

    def _abs_path(self, item) -> str:
        """Absolute path to the item's file (public or restricted storage)."""
        return os.path.join(self._dir_for(item.access), item.filename)

    def file_path(self, item) -> str:
        """Public accessor for the item's absolute file path."""
        return self._abs_path(item)

    def protected_dir(self) -> str:
        """Public accessor for the restricted storage directory."""
        return self._protected_dir()

    def _dir_for(self, access: str) -> str:
        if access == "restricted":
            return self._protected_dir()
        return os.path.join(current_app.static_folder, "uploads")

    def _ensure_dir_for(self, access: str) -> str:
        if access == "restricted":
            return self._ensure_protected_dir()
        return self._upload_dir()

    def _protected_dir(self) -> str:
        """Restricted files live OUTSIDE static/ so the web server never
        exposes them; only /media/file/<id> can send them, after the owning
        feature's access resolver allows it.

        Resolve only. Creating it here would let an unmounted volume in
        production look like an empty directory, turning every protected
        download into a 404 that reads as "the access control is working".
        Writers call _ensure_protected_dir instead.
        """
        return current_app.config.get("PROTECTED_UPLOADS_DIR") or os.path.join(
            current_app.instance_path, "protected_uploads"
        )

    def _ensure_protected_dir(self) -> str:
        d = self._protected_dir()
        os.makedirs(d, exist_ok=True)
        return d

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

        # Collision-safe filename in the storage the ORIGINAL lives in. A crop
        # of a restricted item is the same protected content at another size,
        # so it must never land in static/ as a public file.
        upload_dir = self._ensure_dir_for(item.access)
        candidate = self._collision_safe_name(upload_dir, f"{base}-cropped{out_ext}")

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
            url=f"/static/uploads/{candidate}" if item.is_public else "",
            source_url=item.source_url or "",
            alt=item.alt or "",
            title=f"{item.title or item.filename} (cropped)",
            mime_type=mime,
            size=os.path.getsize(out_path),
            uploaded_at=datetime.utcnow(),
            access=item.access,
            in_gallery=item.in_gallery,
            thumbnail=(self.make_thumbnail(candidate) if item.is_public else ""),
            owner_feature=item.owner_feature,
            owner_ref=item.owner_ref,
        )
        db.session.add(new_item)
        if not item.is_public:
            db.session.flush()
            new_item.url = f"/media/file/{new_item.id}"
        db.session.commit()
        return new_item

    def _upload_dir(self) -> str:
        d = os.path.join(current_app.static_folder, "uploads")
        os.makedirs(d, exist_ok=True)
        return d

    THUMB_MAX = 600  # longest side of a gallery thumbnail, px

    def _thumbs_dir(self) -> str:
        d = os.path.join(self._upload_dir(), "thumbs")
        os.makedirs(d, exist_ok=True)
        return d

    def make_thumbnail(self, filename: str) -> str:
        """Create a web-sized thumbnail for a PUBLIC image already in
        static/uploads/, returning its filename under uploads/thumbs/ (or ""
        if it is not an image or cannot be read). Idempotent by name."""
        src = os.path.join(self._upload_dir(), filename)
        if not os.path.isfile(src):
            return ""
        base, ext = os.path.splitext(filename)
        ext = (ext or ".jpg").lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            return ""
        thumb_name = f"{base}.jpg" if ext in (".jpg", ".jpeg") else f"{base}{ext}"
        dest = os.path.join(self._thumbs_dir(), thumb_name)
        try:
            from PIL import Image

            with Image.open(src) as im:
                im.thumbnail((self.THUMB_MAX, self.THUMB_MAX), Image.LANCZOS)
                if ext in (".jpg", ".jpeg"):
                    im = im.convert("RGB")
                    im.save(dest, "JPEG", quality=82, optimize=True)
                elif ext == ".png":
                    im.save(dest, "PNG", optimize=True)
                elif ext == ".webp":
                    im.save(dest, "WEBP", quality=82)
                else:
                    im.save(dest)
        except Exception:
            return ""
        return thumb_name

    def _collision_safe_name(self, upload_dir: str, filename: str) -> str:
        """Return filename, counter-suffixed if it already exists in the dir."""
        base, ext = os.path.splitext(filename)
        candidate, i = filename, 1
        while os.path.exists(os.path.join(upload_dir, candidate)):
            i += 1
            candidate = f"{base}-{i}{ext}"
        return candidate

    def save_upload(
        self,
        file_storage,
        title: str = "",
        alt: str = "",
        access: str = "public",
        owner_feature: str = "",
        owner_ref: str = "",
        in_gallery: bool = True,
    ):
        """Persist an uploaded file and record it.

        Public files (the default, unchanged behaviour) go to static/uploads/
        and are served as static assets. Restricted files go to the protected
        directory and are only reachable through /media/file/<id>, guarded by
        the owner feature's access resolver.
        """
        filename = secure_filename(file_storage.filename or "")
        if not filename:
            return None
        if access not in ("public", "restricted"):
            return None
        if access == "restricted" and not owner_feature:
            # An unclaimed restricted file could never be served (deny by
            # default), which always means a caller bug. Refuse early.
            return None

        upload_dir = self._ensure_dir_for(access)
        base = os.path.splitext(filename)[0]
        candidate = self._collision_safe_name(upload_dir, filename)

        path = os.path.join(upload_dir, candidate)
        file_storage.save(path)

        item = MediaItem(
            filename=candidate,
            url=f"/static/uploads/{candidate}" if access == "public" else "",
            alt=alt,
            title=title or base,
            mime_type=file_storage.mimetype or "",
            size=os.path.getsize(path),
            uploaded_at=datetime.utcnow(),
            access=access,
            owner_feature=owner_feature or None,
            owner_ref=owner_ref or None,
            in_gallery=bool(in_gallery) and access == "public",
        )
        if access == "public" and (file_storage.mimetype or "").startswith("image/"):
            item.thumbnail = self.make_thumbnail(candidate)
        db.session.add(item)
        if access == "restricted":
            # The canonical URL of a restricted file is its serving route,
            # which needs the id, so flush before building it.
            db.session.flush()
            item.url = f"/media/file/{item.id}"
        db.session.commit()
        return item

    def import_from_url(self, url: str, title: str = "", alt: str = "", in_gallery: bool = False):
        """Download an external image into the media library and record it.

        Idempotent by ``source_url``: importing the same URL twice returns the
        existing item. Used to pull remote images (team photos, post thumbnails…)
        into the local library so they are served from the product, not a 3rd
        party — the WordPress "Media Library" behaviour. Pass ``in_gallery=True``
        when the file is a photo visitors should browse.
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
        base = os.path.splitext(filename)[0]
        candidate = self._collision_safe_name(upload_dir, filename)

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
            in_gallery=bool(in_gallery),
        )
        if (content_type or "").startswith("image/"):
            item.thumbnail = self.make_thumbnail(candidate)
        db.session.add(item)
        db.session.commit()
        return item

    def import_from_file(self, path, *, title="", alt="", source_key=None, in_gallery=False):
        """Copy a local file into the media library and record it.

        The seed-time sibling of ``import_from_url``: seeders bundle images
        inside their feature package and register them here to obtain a public
        URL. Idempotent by ``source_url`` (the caller's ``source_key``, or the
        absolute source path), so re-running a seeder returns the existing item
        instead of duplicating the file. Bundled files are illustrations
        (logos, posters, portraits), so they stay out of the public gallery
        unless the caller says ``in_gallery=True``.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Media import source does not exist: {path}")

        source_url = source_key or "file://" + os.path.abspath(path)
        existing = MediaItem.query.filter_by(source_url=source_url).first()
        if existing:
            return existing

        filename = secure_filename(os.path.basename(path)) or "file"
        upload_dir = self._upload_dir()
        base = os.path.splitext(filename)[0]
        candidate = self._collision_safe_name(upload_dir, filename)

        dest = os.path.join(upload_dir, candidate)
        shutil.copyfile(path, dest)

        item = MediaItem(
            filename=candidate,
            url=f"/static/uploads/{candidate}",
            source_url=source_url,
            alt=alt,
            title=title or base.replace("-", " ").replace("_", " ").strip(),
            mime_type=mimetypes.guess_type(candidate)[0] or "",
            size=os.path.getsize(dest),
            uploaded_at=datetime.utcnow(),
            in_gallery=bool(in_gallery),
        )
        if (item.mime_type or "").startswith("image/"):
            item.thumbnail = self.make_thumbnail(candidate)
        db.session.add(item)
        db.session.commit()
        return item

    def delete_item(self, item_id: int) -> bool:
        item = self.repository.get_by_id(item_id)
        if not item:
            return False
        try:
            path = self._abs_path(item)
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        db.session.delete(item)
        db.session.commit()
        return True
