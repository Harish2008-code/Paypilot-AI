(function () {
  "use strict";

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  async function api(path, options) {
    const config = options || {};
    const headers = Object.assign({ "X-Requested-With": "XMLHttpRequest" }, config.headers || {});
    if (config.method && config.method.toUpperCase() !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = window.PayPilot.csrfToken || getCookie("csrftoken");
    }
    const response = await fetch(path, Object.assign({}, config, { headers, credentials: "same-origin" }));
    let payload;
    try { payload = await response.json(); } catch (_) { payload = { ok: false, error: "The server returned an unexpected response." }; }
    if (!response.ok || !payload.ok) {
      const error = new Error(payload.error || "Something went wrong. Please try again.");
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function money(value, currency) {
    const number = Number(value || 0);
    const code = currency || (window.PayPilot && window.PayPilot.currency) || "USD";
    try {
      return new Intl.NumberFormat("en-US", { style: "currency", currency: code, maximumFractionDigits: 2 }).format(number);
    } catch (_) {
      return `$${number.toFixed(2)}`;
    }
  }

  function toast(message, kind) {
    const region = document.getElementById("toast-region");
    if (!region) return;
    const toastElement = document.createElement("div");
    toastElement.className = `toast ${kind || ""}`;
    toastElement.textContent = message;
    region.appendChild(toastElement);
    window.setTimeout(function () {
      toastElement.style.opacity = "0";
      toastElement.style.transform = "translateY(5px)";
      window.setTimeout(function () { toastElement.remove(); }, 190);
    }, 4300);
  }

  function setLoading(element, on) {
    if (!element) return;
    element.classList.toggle("is-loading", Boolean(on));
    if ("disabled" in element) element.disabled = Boolean(on);
  }

  function updateCartBadge(cart) {
    const count = cart && Number.isFinite(Number(cart.count)) ? cart.count : 0;
    document.querySelectorAll("#cart-count").forEach(function (node) { node.textContent = count; });
  }

  window.PayPilotApp = { api, escapeHtml, money, toast, setLoading, updateCartBadge };

  const menu = document.querySelector(".mobile-menu");
  const sidebar = document.querySelector(".sidebar");
  if (menu && sidebar) {
    menu.addEventListener("click", function () { sidebar.classList.toggle("open"); });
    document.addEventListener("click", function (event) {
      if (window.innerWidth > 900 || !sidebar.classList.contains("open")) return;
      if (!sidebar.contains(event.target) && event.target !== menu) sidebar.classList.remove("open");
    });
  }
}());
