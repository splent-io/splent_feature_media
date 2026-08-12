"""
Integration tests for MediaService.import_from_file.

import_from_file is the seed-time sibling of import_from_url: a seeder copies
an image bundled inside a feature package into the public uploads directory
and records it. The contract under test is that a fresh import creates both
the file and the row, that repeating it with the same source_key returns the
existing row without duplicating the file, and that a missing source path
fails loudly instead of seeding a broken URL.
"""

import os

import pytest

from splent_io.splent_feature_media.models import MediaItem
from splent_io.splent_feature_media.services import MediaService


@pytest.fixture
def source_image(tmp_path):
    path = tmp_path / "team-photo.png"
    path.write_bytes(b"\x89PNG fake body")
    return str(path)


def test_fresh_import_creates_file_and_row(test_client, test_app, source_image):
    with test_app.app_context():
        item = MediaService().import_from_file(
            source_image, source_key="seed://tests/team-photo.png"
        )
        assert item is not None
        assert item.id is not None
        # Uploads survive the per-test database reset, so a repeated run gets
        # a collision-safe suffix. Match on the stem, not the exact name.
        assert item.filename.startswith("team-photo")
        assert item.url == f"/static/uploads/{item.filename}"
        assert item.source_url == "seed://tests/team-photo.png"
        assert item.mime_type == "image/png"
        assert item.size == os.path.getsize(source_image)
        assert item.title == "team photo"
        dest = os.path.join(test_app.static_folder, "uploads", item.filename)
        assert os.path.isfile(dest)


def test_repeated_import_returns_existing_row_and_file(
    test_client, test_app, source_image
):
    with test_app.app_context():
        service = MediaService()
        first = service.import_from_file(
            source_image, source_key="seed://tests/idempotent.png"
        )
        uploads = os.path.join(test_app.static_folder, "uploads")
        files_after_first = set(os.listdir(uploads))

        again = service.import_from_file(
            source_image, source_key="seed://tests/idempotent.png"
        )
        assert again.id == first.id
        assert again.filename == first.filename
        assert set(os.listdir(uploads)) == files_after_first
        assert (
            MediaItem.query.filter_by(
                source_url="seed://tests/idempotent.png"
            ).count()
            == 1
        )


def test_default_source_key_is_the_absolute_path(test_client, test_app, source_image):
    with test_app.app_context():
        item = MediaService().import_from_file(source_image)
        assert item.source_url == "file://" + os.path.abspath(source_image)


def test_missing_source_path_raises(test_client, test_app):
    with test_app.app_context():
        with pytest.raises(FileNotFoundError):
            MediaService().import_from_file("/nowhere/missing.png")
