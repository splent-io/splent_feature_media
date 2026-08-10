"""Template hooks for splent_feature_media — adds a "Media" entry to the
authenticated admin sidebar, pointing at the media library."""

from flask import url_for
from flask_babel import gettext as _

from splent_framework.hooks.template_hooks import register_template_hook


def media_admin_link():
    return (
        '<li class="sidebar-item">'
        f'<a class="sidebar-link" href="{url_for("media.admin_index")}">'
        '<i class="align-middle" data-feather="image"></i> '
        f'<span class="align-middle">{_("Media")}</span></a>'
        "</li>"
    )


register_template_hook("layout.authenticated_sidebar", media_admin_link)
