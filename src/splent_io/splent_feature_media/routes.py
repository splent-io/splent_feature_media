from flask import (
    abort,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_babel import gettext as _
from flask_login import current_user

from splent_io.splent_feature_media import media_bp
from splent_framework.decorators.decorators import role_required
from splent_framework.services.file_access import (
    resolve_file_access,
    send_protected_file,
)
from splent_framework.services.service_locator import service_proxy
from splent_framework.settings.settings_schema import get_config

media_service = service_proxy("MediaService")

# The library holds restricted material, so managing it is a privileged job.
# The auth migration backfills pre-existing accounts to admin, so products
# that upgrade keep exactly the access they had.
MEDIA_ADMIN_ROLES = ("admin", "staff")


# ── Public gallery (themed) ──────────────────────────────────────────────
def _gallery_cfg():
    """The gallery's admin-editable behaviour (panel, then env, then
    defaults), sanitised so a stray value never breaks the page."""
    cfg = get_config("media")
    try:
        page_size = int(cfg.get("gallery_page_size", 48) or 48)
    except (TypeError, ValueError):
        page_size = 48
    try:
        seconds = int(cfg.get("slideshow_seconds", 4) or 4)
    except (TypeError, ValueError):
        seconds = 4
    view = cfg.get("gallery_view", "grid")
    return {
        "public": bool(cfg.get("public_gallery", True)),
        "page_size": max(6, min(page_size, 200)),
        "slideshow_ms": max(1, min(seconds, 60)) * 1000,
        "view": view if view in ("grid", "mosaic") else "grid",
        "upload_in_gallery": bool(cfg.get("upload_in_gallery", True)),
    }


@media_bp.route("/media", methods=["GET"])
def gallery():
    # Products can disable the public gallery when the library holds course
    # material instead of a public showcase. Read at request time through the
    # declarative settings (panel value first, MEDIA_PUBLIC_GALLERY second).
    cfg = _gallery_cfg()
    if not cfg["public"]:
        abort(404)
    items, has_more = media_service.gallery_page(1, cfg["page_size"])
    return render_template(
        "media/gallery.html",
        items=items,
        has_more=has_more,
        total=media_service.count_gallery(),
        page=1,
        gallery=cfg,
    )


@media_bp.route("/media/page/<int:page>", methods=["GET"])
def gallery_page(page):
    """One more page of the gallery as an HTML fragment (infinite scroll).

    Same items markup as the first page, so the lightbox and the grid treat
    appended photos exactly like the initial ones. The response carries the
    next page number in the X-Next-Page header (empty when there is none).
    """
    cfg = _gallery_cfg()
    if not cfg["public"]:
        abort(404)
    items, has_more = media_service.gallery_page(page, cfg["page_size"])
    if not items:
        abort(404)
    html = render_template("media/_gallery_items.html", items=items)
    resp = make_response(html)
    resp.headers["X-Next-Page"] = str(page + 1) if has_more else ""
    return resp


# ── Protected file serving ───────────────────────────────────────────────
@media_bp.route("/media/file/<int:item_id>", methods=["GET"])
def serve_file(item_id):
    """Serve a media file with access control.

    Restricted files are only sent when the owning feature's registered
    resolver allows the current user; everything else is 404, never 403,
    so an unreleased file is indistinguishable from a missing one.
    """
    item = media_service.get(item_id)
    if item is None:
        abort(404)
    if item.is_public:
        # Rebuilt from the filename rather than trusting the stored url, which
        # is an ordinary column: a written-into url would otherwise make this
        # unauthenticated endpoint an open redirect.
        return redirect(f"/static/uploads/{item.filename}")
    if not resolve_file_access(item, current_user):
        abort(404)
    return send_protected_file(
        media_service.file_path(item),
        media_service.protected_dir(),
        mimetype=item.mime_type or "",
        download_name=item.filename,
    )


# ── Admin media library (back-office) ────────────────────────────────────
@media_bp.route("/admin/media", methods=["GET"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_index():
    # The back-office manages protected material too, which is why it is
    # role-gated and why it is the one listing that shows restricted items.
    return render_template(
        "media/admin.html",
        items=media_service.list_all_recent(),
        upload_in_gallery=_gallery_cfg()["upload_in_gallery"],
    )


@media_bp.route("/admin/media/upload", methods=["POST"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_upload():
    file = request.files.get("file")
    if file and file.filename:
        media_service.save_upload(
            file,
            title=request.form.get("title", ""),
            alt=request.form.get("alt", ""),
            in_gallery=bool(request.form.get("in_gallery")),
        )
        flash(_("Media uploaded."), "success")
    else:
        flash(_("No file selected."), "warning")
    return redirect(url_for("media.admin_index"))


@media_bp.route("/admin/media/<int:item_id>", methods=["GET", "POST"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_detail(item_id):
    item = media_service.get(item_id)
    if item is None:
        abort(404)

    if request.method == "POST":
        media_service.update_meta(
            item,
            alt=request.form.get("alt", ""),
            title=request.form.get("title", ""),
            in_gallery=bool(request.form.get("in_gallery")),
        )
        flash(_("Media details saved."), "success")
        return redirect(url_for("media.admin_detail", item_id=item.id))

    dimensions = media_service.dimensions(item)
    return render_template("media/admin_detail.html", item=item, dimensions=dimensions)


@media_bp.route("/admin/media/<int:item_id>/crop", methods=["POST"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_crop(item_id):
    item = media_service.get(item_id)
    if item is None:
        abort(404)
    if not item.is_image:
        return jsonify(error="Only images can be cropped."), 400

    # The client (Cropper.js getCroppedCanvas) has already baked rotation + crop
    # into the uploaded image. We just validate and persist it as a new item.
    upload = request.files.get("image")
    if upload is None:
        return jsonify(error="No image data received."), 400

    new_item = media_service.save_cropped(item, upload)
    if new_item is None:
        return jsonify(error="Could not crop this image."), 400

    return jsonify(url=url_for("media.admin_detail", item_id=new_item.id))


@media_bp.route("/admin/media/<int:item_id>/gallery", methods=["POST"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_toggle_gallery(item_id):
    """Put one item in the public gallery or take it out (list-view switch)."""
    item = media_service.get(item_id)
    if item is None:
        abort(404)
    media_service.set_in_gallery(item, not item.in_gallery)
    flash(
        _("Shown in the public gallery.") if item.in_gallery else _("Hidden from the public gallery."),
        "success",
    )
    return redirect(request.referrer or url_for("media.admin_index"))


@media_bp.route("/admin/media/<int:item_id>/delete", methods=["POST"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_delete(item_id):
    media_service.delete_item(item_id)
    flash(_("Media deleted."), "success")
    return redirect(url_for("media.admin_index"))
