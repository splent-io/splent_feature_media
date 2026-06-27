"""
Functional tests for splent_feature_media.

Functional tests use Flask's test client to exercise full HTTP
request/response cycles (GET, POST, redirects, rendered HTML).
"""


def test_index_is_reachable(test_client):
    """Verify the feature index route exists (200 if public, 302 if login required)."""
    response = test_client.get("/media")
    assert response.status_code in (200, 302)
