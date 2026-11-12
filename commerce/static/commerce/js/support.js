(function () {
  "use strict";
  const app = window.PayPilotApp;
  if (!app) return;
  const paymentsNode = document.getElementById("support-payments");
  const payments = paymentsNode ? JSON.parse(paymentsNode.textContent) : [];
  const paymentById = Object.fromEntries(payments.map(function (payment) { return [String(payment.id), payment]; }));
  const select = document.getElementById("support-payment-select");
  const hint = document.getElementById("selected-order-hint");
  const form = document.getElementById("support-form");
  const message = document.getElementById("support-message");
  const chat = document.getElementById("support-chat");
  const refundReview = document.getElementById("refund-review");
  const refundButton = document.getElementById("refund-button");
  let lastRefundCandidate = null;

  function updateHint() {
    const payment = paymentById[String(select && select.value || "")];
    if (!hint) return;
    if (!payment) {
      hint.innerHTML = "<span>⌁</span><p>Select an order to ground the AI response in its local PayPal status.</p>";
      return;
    }
    hint.innerHTML = `<span>✓</span><p><b>${app.escapeHtml(payment.order_id)}</b> is locally recorded as <b>${app.escapeHtml(payment.status)}</b> · ${app.escapeHtml(payment.currency)} ${app.escapeHtml(payment.amount)}. This is context, not an automatic action.</p>`;
  }
  function append(role, text) {
    if (!chat) return;
    const element = document.createElement("div");
    element.className = `chat-message ${role}`;
    element.innerHTML = role === "assistant" ? `<span class="message-mark">✦</span><div>${app.escapeHtml(text)}</div>` : `<div>${app.escapeHtml(text)}</div>`;
    chat.appendChild(element);
    chat.scrollTop = chat.scrollHeight;
  }
  if (select) { select.addEventListener("change", updateHint); updateHint(); }

  if (form) form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const text = (message.value || "").trim();
    if (!text) return;
    append("user", text);
    message.value = "";
    const submit = form.querySelector("button[type='submit']");
    app.setLoading(submit, true);
    if (refundReview) refundReview.classList.add("hidden");
    lastRefundCandidate = null;
    try {
      const response = await app.api("/api/support/chat/", { method: "POST", body: JSON.stringify({ message: text, payment_id: select && select.value || null }) });
      append("assistant", response.reply);
      if (response.refund_recommended && select && select.value) {
        lastRefundCandidate = paymentById[String(select.value)];
        if (refundReview) refundReview.classList.remove("hidden");
      }
      if (response.mode !== "LLM") app.toast("Support copilot is using guided demo rules; add an LLM key for a model-drafted answer.");
    } catch (error) { app.toast(error.message, "error"); }
    finally { app.setLoading(submit, false); }
  });

  if (refundButton) refundButton.addEventListener("click", async function () {
    if (!lastRefundCandidate) return;
    const confirmation = window.prompt(`This submits a refund of ${lastRefundCandidate.currency} ${lastRefundCandidate.amount} to PayPal. Type REFUND to confirm.`);
    if (confirmation !== "REFUND") { app.toast("Refund was not submitted."); return; }
    app.setLoading(refundButton, true);
    try {
      const response = await app.api(`/api/payments/${encodeURIComponent(lastRefundCandidate.id)}/refund/`, {
        method: "POST",
        body: JSON.stringify({ operator_confirmation: "REFUND", amount: lastRefundCandidate.amount })
      });
      app.toast(response.message, "success");
      if (refundReview) refundReview.classList.add("hidden");
      if (select) {
        const option = select.options[select.selectedIndex];
        if (option) option.textContent = `${response.payment.order_id} · ${response.payment.status} · ${response.payment.currency} ${response.payment.amount}`;
      }
      lastRefundCandidate = null;
    } catch (error) { app.toast(error.message, "error"); }
    finally { app.setLoading(refundButton, false); }
  });
}());
