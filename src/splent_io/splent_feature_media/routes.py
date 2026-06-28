from flask import abort, flash, jsonify, redirect, render_template, request, url_for
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


@media_bp.route("/admin/media/<int:item_id>", methods=["GET", "POST"])
@login_required
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
        flash("Media details saved.", "success")
        return redirect(url_for("media.admin_detail", item_id=item.id))

    dimensions = media_service.dimensions(item)
    return render_template(
        "media/admin_detail.html", item=item, dimensions=dimensions
    )


@media_bp.route("/admin/media/<int:item_id>/crop", methods=["POST"])
@login_required
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
@login_required
def admin_delete(item_id):
    media_service.delete_item(item_id)
    flash("Media deleted.", "success")
    return redirect(url_for("media.admin_index"))
