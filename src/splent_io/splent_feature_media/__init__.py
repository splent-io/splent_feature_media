from splent_framework.blueprints.base_blueprint import create_blueprint
from splent_framework.nav.nav_registry import register_nav_item
from splent_framework.services.service_locator import register_service

from splent_io.splent_feature_media.services import MediaService

media_bp = create_blueprint(__name__)


def init_feature(app):
    from splent_framework.settings.settings_schema import register_settings

    register_service(app, "MediaService", MediaService)
    # Admin-configurable behaviour (framework renders the panel from this
    # schema). MEDIA_NAV_LABEL stays env-only: the nav registers at init
    # time, so a panel value would claim a change it cannot deliver until
    # restart. The storage paths are deployment decisions, not editorial.
    register_settings(
        "media",
        "Media",
        [
            {
                "key": "public_gallery",
                "type": "bool",
                "default": "1",
                "label": "Public gallery",
                "help": "The gallery page at /media, browsable by anyone. Off answers 404 so visitors cannot enumerate the library.",
            },
        ],
        icon="folder",
    )
    # The gallery stays out of the main nav unless the product names it.
    # A photo-heavy site (an event, a lab with a showcase) sets
    # MEDIA_NAV_LABEL to whatever its visitors should read ("Photos",
    # "Fotos", "Gallery") and gets the entry; everyone else keeps /media
    # reachable but unadvertised.
    label = app.config.get("MEDIA_NAV_LABEL", "")
    if label and app.config.get("MEDIA_PUBLIC_GALLERY", True):
        register_nav_item(key="media", label=label, href="/media", order=45)


def inject_context_vars(app):
    return {}
