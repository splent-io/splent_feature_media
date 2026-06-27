from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from splent_io.splent_feature_media import media_bp
from splent_framework.services.service_locator import service_proxy

media_service = service_proxy("MediaService")


# ── Public gallery (themed) ──────────────────────────────────────────────
@media_bp.route("/media", methods=["GET"])
def gallery():
    return render_template("media/gallery.html", items=media_service.list_recent())


# ── Admin media library (back-office) ────────────────────────────────────
@media_bp.route("/admin/media", methods=["GET"])
@login_required
def admin_index():
    return render_template("media/admin.html", items=media_service.list_recent())


@media_bp.route("/admin/media/upload", methods=["POST"])
@login_required
def admin_upload():
    file = request.files.get("file")
    if file and file.filename:
        media_service.save_upload(
            file, title=request.form.get("title", ""), alt=request.form.get("alt", "")
        )
        flash("Media uploaded.", "success")
    else:
        flash("No file selected.", "warning")
    return redirect(url_for("media.admin_index"))


@media_bp.route("/admin/media/<int:item_id>/delete", methods=["POST"])
@login_required
def admin_delete(item_id):
    media_service.delete_item(item_id)
    flash("Media deleted.", "success")
    return redirect(url_for("media.admin_index"))
