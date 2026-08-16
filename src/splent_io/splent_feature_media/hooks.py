"""Template hooks for splent_feature_media.

* ``layout.authenticated_sidebar``: the "Media" entry pointing at the library.
* ``home.section``: the latest public photos on the homepage. Off unless the
  product (or an administrator, in the settings panel) asks for some, so
  installing the library on a site that is not photo-led changes nothing.
"""

from flask import render_template, request, url_for
from flask_babel import gettext as _
from markupsafe import Markup

from splent_framework.hooks.template_hooks import register_template_hook
from splent_framework.services.service_locator import service_proxy
from splent_framework.settings.settings_schema import get_config


def media_admin_link():
    return (
        '<li class="sidebar-item">'
        f'<a class="sidebar-link" href="{url_for("media.admin_index")}">'
        '<i class="align-middle" data-feather="image"></i> '
        f'<span class="align-middle">{_("Media")}</span></a>'
        "</li>"
    )


def media_home_section():
    """The latest public photos, on the homepage only.

    How many is admin-editable ("Photos on the homepage"), zero by default.
    The section links to the gallery page only while that page is public.
    """
    if request.endpoint != "public.index":
        return ""
    cfg = get_config("media")
    try:
        limit = int(cfg.get("home_count", 0) or 0)
    except (TypeError, ValueError):
        limit = 0
    if limit <= 0:
        return ""
    try:
        items = service_proxy("MediaService").list_public_images(limit)
    except Exception:
        return ""
    if not items:
        return ""
    return Markup(
        render_template(
            "media/hooks/home_section.html",
            items=items,
            gallery_public=bool(cfg.get("public_gallery", True)),
        )
    )


register_template_hook("layout.authenticated_sidebar", media_admin_link)
register_template_hook("home.section", media_home_section, order=40)
