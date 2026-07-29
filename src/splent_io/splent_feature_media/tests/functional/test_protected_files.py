"""
Functional tests for protected file serving.

The contract under test is deny by default: a restricted file whose owner
registered no resolver, or whose resolver denies, answers 404 to the exact
URL, indistinguishable from a missing file. Only a granting resolver makes
the bytes reachable. Public items and the public gallery keep their old
behaviour.
"""

import io
import os

import pytest
from werkzeug.datastructures import FileStorage

from splent_framework.services.file_access import (
    clear_file_access_resolvers,
    register_file_access_resolver,
)
from splent_io.splent_feature_media.services import MediaService


@pytest.fixture(autouse=True)
def _clean_resolvers():
    clear_file_access_resolvers()
    yield
    clear_file_access_resolvers()


def _png_bytes() -> bytes:
    """A real 2x2 PNG, because the crop path decodes with Pillow."""
    Image = pytest.importorskip("PIL.Image", reason="Pillow not installed")

    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, "PNG")
    return buffer.getvalue()


def _upload(
    test_app,
    access,
    owner_feature="tests",
    filename="secret.pdf",
    content_type="application/pdf",
    body=b"%PDF-1.4 dummy body",
):
    with test_app.app_context():
        storage = FileStorage(
            stream=io.BytesIO(body),
            filename=filename,
            content_type=content_type,
        )
        item = MediaService().save_upload(
            storage,
            title=filename,
            access=access,
            owner_feature=owner_feature if access == "restricted" else "",
            owner_ref="document:1" if access == "restricted" else "",
        )
        assert item is not None
        return item.id, item.url


def test_restricted_file_without_resolver_is_404(test_client, test_app):
    item_id, url = _upload(test_app, "restricted")
    assert url == f"/media/file/{item_id}"
    response = test_client.get(url)
    assert response.status_code == 404


def test_restricted_file_with_denying_resolver_is_404(test_client, test_app):
    item_id, url = _upload(test_app, "restricted")
    register_file_access_resolver("tests", lambda item, user: False)
    assert test_client.get(url).status_code == 404


def test_restricted_file_with_granting_resolver_serves_bytes(test_client, test_app):
    item_id, url = _upload(test_app, "restricted")
    register_file_access_resolver("tests", lambda item, user: True)
    response = test_client.get(url)
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF-1.4")
    assert response.mimetype == "application/pdf"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "private, no-store"


def test_uploader_chosen_html_type_is_never_served_inline(test_client, test_app):
    # The stored mime comes from the multipart header the client chose, so
    # serving it back would be stored XSS on the product's own origin
    # against exactly the staff allowed to read protected files.
    item_id, url = _upload(
        test_app,
        "restricted",
        filename="notes.html",
        content_type="text/html",
        body=b"<script>alert(1)</script>",
    )
    register_file_access_resolver("tests", lambda item, user: True)
    response = test_client.get(url)
    assert response.status_code == 200
    assert response.mimetype == "application/octet-stream"
    assert response.headers["Content-Disposition"].startswith("attachment")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_restricted_upload_requires_an_owner(test_app):
    with test_app.app_context():
        storage = FileStorage(
            stream=io.BytesIO(b"orphan"),
            filename="orphan.pdf",
            content_type="application/pdf",
        )
        assert MediaService().save_upload(storage, access="restricted") is None


def test_public_file_redirects_to_static(test_client, test_app):
    item_id, url = _upload(test_app, "public", filename="poster.png")
    assert url.startswith("/static/uploads/")
    response = test_client.get(f"/media/file/{item_id}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(url)


def test_gallery_lists_only_public_items(test_client, test_app):
    # Both are images because the gallery template only renders images; the
    # restricted one must not leak into the anonymous listing in any form,
    # neither its serving URL nor its name.
    hidden_id, _ = _upload(
        test_app,
        "restricted",
        filename="hidden-exam.png",
        content_type="image/png",
        body=b"\x89PNG fake",
    )
    _upload(
        test_app,
        "public",
        filename="banner.png",
        content_type="image/png",
        body=b"\x89PNG fake",
    )
    response = test_client.get("/media")
    assert response.status_code == 200
    assert f"/media/file/{hidden_id}".encode() not in response.data
    assert b"hidden-exam" not in response.data
    assert b"banner" in response.data


def test_cropping_a_restricted_item_stays_restricted(test_client, test_app):
    # A crop is the same protected content at another size. Landing it in
    # static/uploads as a public item would publish an unreleased exam scan
    # through a routine staff action.
    item_id, _ = _upload(
        test_app,
        "restricted",
        filename="exam-scan.png",
        content_type="image/png",
        body=_png_bytes(),
    )
    with test_app.app_context():
        service = MediaService()
        source = service.get(item_id)
        crop = FileStorage(
            stream=io.BytesIO(_png_bytes()),
            filename="crop.png",
            content_type="image/png",
        )
        new_item = service.save_cropped(source, crop)
        assert new_item is not None
        assert new_item.access == "restricted"
        assert new_item.owner_feature == source.owner_feature
        assert new_item.owner_ref == source.owner_ref
        assert new_item.url == f"/media/file/{new_item.id}"
        assert not os.path.exists(
            os.path.join(test_app.static_folder, "uploads", new_item.filename)
        )
        new_id = new_item.id

    assert test_client.get(f"/media/file/{new_id}").status_code == 404


def test_pickers_never_see_restricted_items(test_app):
    # list_recent is what post, slider and partners feed their shared picker
    # with, so it must not expose protected material to a public page.
    _upload(test_app, "restricted", filename="solutions.pdf")
    _upload(test_app, "public", filename="cover.png", content_type="image/png")
    with test_app.app_context():
        # Uploads survive the per-test database reset, so a repeated run gets
        # a collision-safe suffix. Match on the stem, not the exact name.
        names = [item.filename for item in MediaService().list_recent()]
        assert any(name.startswith("cover") for name in names)
        assert not any(name.startswith("solutions") for name in names)


def test_gallery_can_be_disabled_per_product(test_client, test_app):
    original = test_app.config.get("MEDIA_PUBLIC_GALLERY", True)
    test_app.config["MEDIA_PUBLIC_GALLERY"] = False
    try:
        assert test_client.get("/media").status_code == 404
    finally:
        test_app.config["MEDIA_PUBLIC_GALLERY"] = original
