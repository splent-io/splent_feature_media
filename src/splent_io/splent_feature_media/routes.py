from flask import (
    abort,
    flash,
    jsonify,
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
@media_bp.route("/media", methods=["GET"])
def gallery():
    # Products can disable the public gallery when the library holds course
    # material instead of a public showcase. Read at request time through the
    # declarative settings (panel value first, MEDIA_PUBLIC_GALLERY second).
    if not get_config("media").get("public_gallery", True):
        abort(404)
    return render_template(
        "media/gallery.html", items=media_service.list_public_recent()
    )


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
    return render_template("media/admin.html", items=media_service.list_all_recent())


@media_bp.route("/admin/media/upload", methods=["POST"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_upload():
    file = request.files.get("file")
    if file and file.filename:
        media_service.save_upload(
            file, title=request.form.get("title", ""), alt=request.form.get("alt", "")
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


@media_bp.route("/admin/media/<int:item_id>/delete", methods=["POST"])
@role_required(*MEDIA_ADMIN_ROLES)
def admin_delete(item_id):
    media_service.delete_item(item_id)
    flash(_("Media deleted."), "success")
    return redirect(url_for("media.admin_index"))
