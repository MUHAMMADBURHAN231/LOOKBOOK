/*!
 * LOOKBOOK live try-on widget.
 *
 * 1. Add the script once:
 *      <script src="https://YOUR-LOOKBOOK-HOST/widget.js" data-lookbook-key="pk_live_..." async></script>
 * 2. Mark any button or link as a trigger:
 *      <button data-lookbook-garment="tailored navy wool blazer"
 *              data-lookbook-name="Tailored Blazer"
 *              data-lookbook-image="https://yourstore.com/blazer.jpg">Try it on</button>
 *
 * The key is a publishable key: it only works on the origins registered for your store, and the
 * try-on window refuses to load anywhere else (CSP frame-ancestors).
 */
(function () {
  if (window.__lookbookWidget) return;
  window.__lookbookWidget = true;

  var script = document.currentScript;
  var origin = new URL(script ? script.src : location.href).origin;
  var storeKey = (script && script.getAttribute("data-lookbook-key")) || "";
  var SELECTOR = "[data-lookbook-garment]";
  var overlay = null;
  var lastTrigger = null;

  function absolute(url) {
    try {
      return new URL(url, location.href).href;
    } catch {
      return "";
    }
  }

  function open(el) {
    close();
    lastTrigger = el;
    var params = new URLSearchParams({
      key: el.getAttribute("data-lookbook-key") || storeKey,
      garment: el.getAttribute("data-lookbook-garment") || "",
      name: el.getAttribute("data-lookbook-name") || el.getAttribute("data-lookbook-garment") || "",
      host: location.origin,
    });
    var image = el.getAttribute("data-lookbook-image");
    if (image) params.set("image", absolute(image));

    overlay = document.createElement("div");
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Live try-on");
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:2147483647;background:rgba(6,8,10,.72);" +
      "display:flex;align-items:center;justify-content:center;padding:16px";

    var frame = document.createElement("iframe");
    frame.src = origin + "/embed?" + params.toString();
    frame.allow = "camera; autoplay; fullscreen";
    frame.title = "Live virtual try-on";
    frame.style.cssText =
      "width:min(880px,100%);height:min(640px,100%);border:1px solid #34414b;background:#0b0f12";

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Close try-on");
    closeBtn.textContent = "×";
    closeBtn.style.cssText =
      "position:absolute;top:12px;right:16px;width:44px;height:44px;border:1px solid #34414b;" +
      "background:#06080a;color:#e9eef1;font:24px/40px monospace;cursor:pointer";
    closeBtn.onclick = close;

    overlay.onclick = function (e) {
      if (e.target === overlay) close();
    };
    overlay.appendChild(frame);
    overlay.appendChild(closeBtn);
    document.body.appendChild(overlay);
    closeBtn.focus();
  }

  function close() {
    if (overlay) overlay.remove();
    overlay = null;
    if (lastTrigger) lastTrigger.focus();
    lastTrigger = null;
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
