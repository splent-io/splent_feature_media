from splent_framework.blueprints.base_blueprint import create_blueprint
from splent_framework.nav.nav_registry import register_nav_item
from splent_framework.services.service_locator import register_service

from splent_io.splent_feature_media.services import MediaService

media_bp = create_blueprint(__name__)


def init_feature(app):
    register_service(app, "MediaService", MediaService)
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
