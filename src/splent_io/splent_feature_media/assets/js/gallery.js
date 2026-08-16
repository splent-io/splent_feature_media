/* The public gallery: infinite scroll and the view switcher.
 *
 * Markup contract (templates/media/gallery.html):
 *   .gallery-grid[data-lightbox-gallery][data-gallery-next=<url of page 2>]
 *   [data-gallery-sentinel] with a [data-gallery-more] link (works without JS)
 *   .gallery-toolbar with [data-gallery-view=grid|mosaic] and [data-gallery-slideshow]
 *
 * Pages come from /media/page/<n> as bare items; the X-Next-Page header
 * says whether another one follows. The theme's lightbox is told when the
 * grid grows so a running slideshow keeps going through the new photos.
 */
(function () {
    "use strict";

    var grid = document.querySelector(".gallery-grid[data-gallery-next], .gallery-grid[data-lightbox-gallery]");
    if (!grid) return;
    var sentinel = document.querySelector("[data-gallery-sentinel]");
    var moreLink = document.querySelector("[data-gallery-more]");
    var loading = false;

    function nextUrl() {
        return grid.getAttribute("data-gallery-next") || "";
    }

    function loadMore() {
        var url = nextUrl();
        if (!url || loading) return Promise.resolve(false);
        loading = true;
        grid.setAttribute("aria-busy", "true");
        return fetch(url, { headers: { "X-Requested-With": "fetch" } })
            .then(function (r) {
                if (!r.ok) throw new Error(r.status);
                var next = r.headers.get("X-Next-Page");
                return r.text().then(function (html) { return { html: html, next: next }; });
            })
            .then(function (res) {
                var tpl = document.createElement("template");
                tpl.innerHTML = res.html.trim();
                grid.appendChild(tpl.content);
                if (res.next) {
                    grid.setAttribute("data-gallery-next", url.replace(/\/page\/\d+/, "/page/" + res.next));
                    if (moreLink) moreLink.href = grid.getAttribute("data-gallery-next");
                } else {
                    grid.removeAttribute("data-gallery-next");
                    if (sentinel) sentinel.hidden = true;
                }
                if (window.splentLightbox) window.splentLightbox.refresh();
                return true;
            })
            .catch(function () { return false; })
            .then(function (ok) {
                loading = false;
                grid.removeAttribute("aria-busy");
                return ok;
            });
    }

    /* Infinite scroll: load the next page when the sentinel scrolls into view. */
    if (sentinel && "IntersectionObserver" in window) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) { if (e.isIntersecting) loadMore(); });
        }, { rootMargin: "600px 0px" });
        io.observe(sentinel);
    }
    if (moreLink) {
        moreLink.addEventListener("click", function (e) { e.preventDefault(); loadMore(); });
    }

    /* View switcher: grid (uniform tiles) or mosaic (natural proportions). */
    document.querySelectorAll("[data-gallery-view]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var view = btn.getAttribute("data-gallery-view");
            grid.classList.toggle("gallery-grid--mosaic", view === "mosaic");
            document.querySelectorAll("[data-gallery-view]").forEach(function (b) {
                var on = b === btn;
                b.classList.toggle("is-active", on);
                b.setAttribute("aria-pressed", on ? "true" : "false");
            });
            try { localStorage.setItem("splent.gallery.view", view); } catch (err) { /* private mode */ }
        });
    });
    try {
        var saved = localStorage.getItem("splent.gallery.view");
        var savedBtn = saved && document.querySelector('[data-gallery-view="' + saved + '"]');
        if (savedBtn) savedBtn.click();
    } catch (err) { /* private mode */ }

    /* Slideshow: open the lightbox on the first photo, playing. */
    var play = document.querySelector("[data-gallery-slideshow]");
    if (play) {
        play.addEventListener("click", function () {
            var first = grid.querySelector("img");
            if (first && window.splentLightbox) window.splentLightbox.open(first, { play: true });
        });
    }

    /* A slideshow that reaches the last loaded photo asks for the next page
       and carries on; when there is none it wraps around. */
    grid.addEventListener("splent:lightbox:end", function () {
        loadMore().then(function (ok) {
            if (ok && window.splentLightbox) window.splentLightbox.next();
        });
    });
})();
