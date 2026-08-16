"""
Functional tests for splent_feature_media.

Functional tests use Flask's test client to exercise full HTTP
request/response cycles (GET, POST, redirects, rendered HTML).
"""


def test_index_is_reachable(test_client):
    """Verify the feature index route exists (200 if public, 302 if login required)."""
    response = test_client.get("/media")
    assert response.status_code in (200, 302)


def _seed_gallery(app, n_in=3, n_out=2):
    """A few public images, some in the gallery and some kept out of it."""
    from splent_framework.db import db
    from splent_io.splent_feature_media.models import MediaItem

    with app.app_context():
        for i in range(n_in):
            db.session.add(MediaItem(filename=f"in-{i}.jpg", url=f"/static/uploads/in-{i}.jpg", mime_type="image/jpeg", title=f"Photo {i}", in_gallery=True))
        for i in range(n_out):
            db.session.add(MediaItem(filename=f"out-{i}.png", url=f"/static/uploads/out-{i}.png", mime_type="image/png", title=f"Logo {i}", in_gallery=False))
        db.session.add(MediaItem(filename="doc.pdf", url="/static/uploads/doc.pdf", mime_type="application/pdf", title="Doc", in_gallery=True))
        db.session.commit()


def test_gallery_shows_only_items_flagged_for_it(test_client):
    """Logos, posters and documents stay in the library but out of /media."""
    _seed_gallery(test_client.application)
    response = test_client.get("/media")
    if response.status_code != 200:
        return  # gallery disabled by the product under test
    html = response.data.decode()
    assert "in-0.jpg" in html and "in-2.jpg" in html
    assert "out-0.png" not in html
    assert "doc.pdf" not in html
    assert 'target="_blank"' not in html.split('class="site-nav"')[-1].split("</main>")[0]


def test_gallery_pages_as_fragments_for_infinite_scroll(test_client):
    """/media/page/<n> returns bare items and says whether more follow."""
    _seed_gallery(test_client.application, n_in=60, n_out=0)
    first = test_client.get("/media")
    if first.status_code != 200:
        return
    assert 'data-gallery-next="/media/page/2"' in first.data.decode()
    page2 = test_client.get("/media/page/2")
    assert page2.status_code == 200
    body = page2.data.decode()
    assert "<html" not in body and 'class="gallery-grid__item"' in body
    assert page2.headers.get("X-Next-Page") == ""
    assert test_client.get("/media/page/9").status_code == 404
