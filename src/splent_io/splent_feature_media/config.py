"""
media feature configuration.

Injects environment variables into Flask app.config.
Add your feature's env vars here so the framework can track them.

To regenerate from source code: splent feature:inject-config splent_feature_media
"""

import os


def inject_config(app):
    # An unset or empty value keeps the gallery, so a blank line in a .env
    # cannot silently take a public page down.
    gallery = os.getenv("MEDIA_PUBLIC_GALLERY", "")
    accel_prefix = os.getenv("PROTECTED_FILES_ACCEL_PREFIX", "")

    app.config.update(
        {
            # Public gallery page at /media. Products whose library holds
            # course material rather than a public showcase set this to false
            # so anonymous visitors cannot enumerate the whole library. Also
            # admin-editable in the settings panel, which wins at request time.
            "MEDIA_PUBLIC_GALLERY": gallery.strip().lower() not in ("0", "false", "no"),
            # Main-nav label for the public gallery. Empty keeps the gallery
            # out of the nav; a label ("Photos", "Fotos") adds the entry.
            "MEDIA_NAV_LABEL": os.getenv("MEDIA_NAV_LABEL", "").strip(),
            # Where restricted files live, OUTSIDE static/. Empty means
            # <instance_path>/protected_uploads. In production this path must
            # be a persistent volume.
            "PROTECTED_UPLOADS_DIR": os.getenv("PROTECTED_UPLOADS_DIR", ""),
            # An internal nginx location prefix (for example /_protected)
            # hands protected downloads to nginx via X-Accel-Redirect. That
            # location must be declared internal or the whole protected
            # directory becomes reachable.
            "PROTECTED_FILES_ACCEL_PREFIX": accel_prefix,
            # Latest public photos on the homepage; 0 (the default) shows
            # none. Also admin-editable in the settings panel, which wins.
            "MEDIA_HOME_COUNT": _int_env("MEDIA_HOME_COUNT", 0),
            # Public gallery behaviour; all admin-editable in the panel,
            # which wins over these environment values.
            "MEDIA_GALLERY_VIEW": os.getenv("MEDIA_GALLERY_VIEW", "grid").strip() or "grid",
            "MEDIA_GALLERY_PAGE_SIZE": _int_env("MEDIA_GALLERY_PAGE_SIZE", 48),
            "MEDIA_SLIDESHOW_SECONDS": _int_env("MEDIA_SLIDESHOW_SECONDS", 4),
            "MEDIA_UPLOAD_IN_GALLERY": os.getenv("MEDIA_UPLOAD_IN_GALLERY", "").strip().lower()
            not in ("0", "false", "no"),
        }
    )


def _int_env(name, default):
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default
