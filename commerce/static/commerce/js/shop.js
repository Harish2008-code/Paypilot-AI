(function () {
  "use strict";
  const app = window.PayPilotApp;
  if (!app) return;
  const config = window.PayPilot.paypal || {};
  const catalogNode = document.getElementById("catalog-data");
  const catalog = catalogNode ? JSON.parse(catalogNode.textContent) : [];
  const catalogBySku = Object.fromEntries(catalog.map(function (item) { return [item.sku, item]; }));
  let cart = { items: [], count: 0, total: "0.00", currency: window.PayPilot.currency || "USD" };
  let lastOrderId = null;

  const cartItems = document.getElementById("cart-items");
  const cartSubtotal = document.getElementById("cart-subtotal");
  const cartTotal = document.getElementById("cart-total");
  const panelCount = document.getElementById("cart-panel-count");
  const demoCheckoutButton = document.getElementById("demo-checkout-button");

  function renderCart(nextCart) {
    cart = nextCart || cart;
    app.updateCartBadge(cart);
    if (panelCount) panelCount.textContent = cart.count || 0;
    if (cartSubtotal) cartSubtotal.textContent = app.money(cart.total, cart.currency);
    if (cartTotal) cartTotal.innerHTML = `${app.money(cart.total, cart.currency)} <small>${app.escapeHtml(cart.currency)}</small>`;
    if (!cartItems) return;
    if (!cart.items || !cart.items.length) {
      cartItems.innerHTML = '<div class="empty-cart"><span>＋</span><p>Your recommendations will land here.</p><small>Nothing is charged until the buyer approves in PayPal.</small></div>';
      return;
    }
    cartItems.innerHTML = cart.items.map(function (item) {
      return `<div class="cart-item"><span class="cart-emoji">${app.escapeHtml(item.emoji)}</span><div><b>${app.escapeHtml(item.name)}</b><small>${item.quantity} × ${app.money(item.unit_price, cart.currency)}</small></div><div><strong>${app.money(item.amount, cart.currency)}</strong><button class="remove-cart-item" data-sku="${app.escapeHtml(item.sku)}" aria-label="Remove ${app.escapeHtml(item.name)}">×</button></div></div>`;
    }).join("");
  }

  async function refreshCart() {
    try {
      const response = await app.api("/api/cart/", { method: "GET" });
      renderCart(response.cart);
    } catch (error) { console.warn(error); }
  }

  async function addToCart(sku) {
    try {
      const response = await app.api("/api/cart/add/", { method: "POST", body: JSON.stringify({ sku: sku, quantity: 1 }) });
      renderCart(response.cart);
      app.toast(response.message || "Added to cart.", "success");
    } catch (error) { app.toast(error.message, "error"); }
  }

  async function updateCart(sku, quantity) {
    try {
      const response = await app.api("/api/cart/update/", { method: "POST", body: JSON.stringify({ sku: sku, quantity: quantity }) });
      renderCart(response.cart);
    } catch (error) { app.toast(error.message, "error"); }
  }

  document.querySelectorAll(".add-to-cart").forEach(function (button) {
    button.addEventListener("click", function () { addToCart(button.dataset.sku); });
  });
  if (cartItems) cartItems.addEventListener("click", function (event) {
    const remove = event.target.closest(".remove-cart-item");
    if (remove) updateCart(remove.dataset.sku, 0);
  });

  document.querySelectorAll(".filter-pill").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".filter-pill").forEach(function (pill) { pill.classList.remove("active"); });
      button.classList.add("active");
      const filter = button.dataset.filter;
      document.querySelectorAll(".product-card").forEach(function (card) {
        card.classList.toggle("is-hidden", filter !== "all" && card.dataset.category !== filter);
      });
    });
  });

  const chatLog = document.getElementById("shop-chat-log");
  const chatForm = document.getElementById("shop-chat-form");
  const chatInput = document.getElementById("shop-chat-input");
  function appendMessage(role, text) {
    if (!chatLog) return;
    const item = document.createElement("div");
    item.className = `chat-message ${role}`;
    item.innerHTML = role === "assistant"
      ? `<span class="message-mark">✦</span><div>${app.escapeHtml(text)}</div>`
      : `<div>${app.escapeHtml(text)}</div>`;
    chatLog.appendChild(item);
    chatLog.scrollTop = chatLog.scrollHeight;
  }
  function appendSuggestions(skus) {
    if (!chatLog || !skus || !skus.length) return;
    const available = skus.filter(function (sku) { return catalogBySku[sku]; });
    if (!available.length) return;
    const container = document.createElement("div");
    container.className = "suggestion-chips";
    container.innerHTML = available.map(function (sku) {
      const product = catalogBySku[sku];
      return `<button type="button" data-sku="${app.escapeHtml(sku)}">+ ${app.escapeHtml(product.name)} · ${app.money(product.price, cart.currency)}</button>`;
    }).join("");
    container.addEventListener("click", function (event) {
      const button = event.target.closest("button[data-sku]");
      if (button) addToCart(button.dataset.sku);
    });
    chatLog.appendChild(container);
    chatLog.scrollTop = chatLog.scrollHeight;
  }
  async function askCopilot(message) {
    if (!message) return;
    appendMessage("user", message);
    if (chatInput) chatInput.value = "";
    const submit = chatForm && chatForm.querySelector("button");
    app.setLoading(submit, true);
    try {
      const response = await app.api("/api/assistant/chat/", { method: "POST", body: JSON.stringify({ message: message }) });
      appendMessage("assistant", response.reply);
      appendSuggestions(response.suggested_skus);
      if (response.mode !== "LLM") app.toast("Copilot is using the guided demo brain. Add an LLM key for live model responses.");
    } catch (error) {
      app.toast(error.message, "error");
    } finally { app.setLoading(submit, false); }
  }
  if (chatForm) chatForm.addEventListener("submit", function (event) { event.preventDefault(); askCopilot((chatInput && chatInput.value || "").trim()); });
  document.querySelectorAll("[data-prompt]").forEach(function (button) { button.addEventListener("click", function () { askCopilot(button.dataset.prompt); }); });

  async function createOrder() {
    const response = await app.api("/api/checkout/create/", { method: "POST", body: JSON.stringify({}) });
    lastOrderId = response.id;
    return response;
  }
  async function captureOrder(orderId) {
    const response = await app.api("/api/checkout/capture/", { method: "POST", body: JSON.stringify({ order_id: orderId }) });
    app.toast(response.message, "success");
    renderCart({ items: [], count: 0, total: "0.00", currency: cart.currency });
    return response;
  }
  async function runDemoCheckout() {
    if (!cart.items || !cart.items.length) { app.toast("Your cart is empty—ask the copilot or add an offer first.", "error"); return; }
    app.setLoading(demoCheckoutButton, true);
    try {
      const order = await createOrder();
      if (!order.demo) {
        app.toast("The PayPal approval control is loading. Please try again in a moment.");
        return;
      }
      await captureOrder(order.id);
    } catch (error) {
      app.toast(error.message, "error");
    } finally { app.setLoading(demoCheckoutButton, false); }
  }

  function setupLivePayPal() {
    if (!config.configured || !config.client_id) return;
    if (!demoCheckoutButton) return;
    demoCheckoutButton.disabled = true;
    demoCheckoutButton.textContent = "Loading secure PayPal…";
    const script = document.createElement("script");
    script.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(config.client_id)}&currency=${encodeURIComponent(config.currency || "USD")}&intent=capture&components=buttons`;
    script.async = true;
    script.onload = function () {
      if (!window.paypal || !window.paypal.Buttons) {
        demoCheckoutButton.disabled = false; demoCheckoutButton.textContent = "Pay with PayPal"; return;
      }
      window.paypal.Buttons({
        style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal", height: 40 },
        createOrder: async function () {
          const order = await createOrder();
          return order.id;
        },
        onApprove: async function (data) {
          await captureOrder(data.orderID);
        },
        onError: function (error) {
          console.error("PayPal checkout error", error);
          app.toast("PayPal could not complete checkout. Review your Sandbox setup and try again.", "error");
        }
      }).render("#paypal-live-buttons").then(function () {
        demoCheckoutButton.style.display = "none";
      }).catch(function () {
        demoCheckoutButton.disabled = false;
        demoCheckoutButton.textContent = "Pay with PayPal";
        app.toast("Could not load the PayPal button. Check your client ID and browser network.", "error");
      });
    };
    script.onerror = function () {
      demoCheckoutButton.disabled = false;
      demoCheckoutButton.textContent = "Pay with PayPal";
      app.toast("Could not load the PayPal SDK. Check your network connection.", "error");
    };
    document.head.appendChild(script);
  }
  if (demoCheckoutButton) demoCheckoutButton.addEventListener("click", runDemoCheckout);

  refreshCart();
  setupLivePayPal();
}());
