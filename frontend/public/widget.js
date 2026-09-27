/*!
 * LOOKBOOK live try-on widget.
 *
 * Add one script tag to any store page:
 *   <script src="https://YOUR-LOOKBOOK-HOST/widget.js" async></script>
 *
 * Then mark any button or link as a try-on trigger:
 *   <button data-lookbook-garment="tailored navy wool blazer"
 *           data-lookbook-name="Tailored Blazer"
 *           data-lookbook-image="https://store.example/blazer.jpg">Try it on</button>
 *
 * Empty trigger elements get a default "Try it on live" label.
 */
(function () {
  if (window.__lookbookWidget) return;
  window.__lookbookWidget = true;

  var script = document.currentScript;
  var origin = new URL(script ? script.src : location.href).origin;
  var SELECTOR = "[data-lookbook-garment]";
  var overlay = null;

  function absolute(url) {
    try {
      return new URL(url, location.href).href;
    } catch {
      return "";
    }
  }

  function open(el) {
    close();
    var params = new URLSearchParams({
      garment: el.getAttribute("data-lookbook-garment") || "",
      name: el.getAttribute("data-lookbook-name") || el.getAttribute("data-lookbook-garment") || "",
    });
    var image = el.getAttribute("data-lookbook-image");
    if (image) params.set("image", absolute(image));

    overlay = document.createElement("div");
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.6);" +
      "display:flex;align-items:center;justify-content:center;padding:16px";

    var frame = document.createElement("iframe");
    frame.src = origin + "/embed?" + params.toString();
    frame.allow = "camera; autoplay; fullscreen";
    frame.title = "Live virtual try-on";
    frame.style.cssText =
      "width:min(960px,100%);height:min(680px,100%);border:0;border-radius:16px;background:#fff;" +
      "box-shadow:0 20px 60px rgba(0,0,0,.35)";

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Close try-on");
    closeBtn.textContent = "×";
    closeBtn.style.cssText =
      "position:absolute;top:12px;right:16px;width:40px;height:40px;border:0;border-radius:999px;" +
      "background:#fff;color:#111;font-size:26px;line-height:40px;cursor:pointer";
    closeBtn.onclick = close;

    overlay.onclick = function (e) {
      if (e.target === overlay) close();
    };
    overlay.appendChild(frame);
    overlay.appendChild(closeBtn);
    document.body.appendChild(overlay);
  }

  function close() {
    if (overlay) overlay.remove();
    overlay = null;
  }

  function label(root) {
    (root.querySelectorAll ? root.querySelectorAll(SELECTOR) : []).forEach(function (el) {
      if (!el.textContent.trim() && !el.children.length) el.textContent = "Try it on live";
    });
  }

  // Delegated listener: works for triggers added later (SPAs, lazy-loaded product grids).
  document.addEventListener("click", function (e) {
    var el = e.target.closest && e.target.closest(SELECTOR);
    if (!el) return;
    e.preventDefault();
    open(el);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });
  window.addEventListener("message", function (e) {
    if (e.origin === origin && e.data && e.data.type === "lookbook:close") close();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      label(document);
    });
  } else {
    label(document);
  }
  new MutationObserver(function () {
    label(document);
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
