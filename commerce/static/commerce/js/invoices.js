(function () {
  "use strict";
  const app = window.PayPilotApp;
  if (!app) return;
  const form = document.getElementById("invoice-form");
  const draftButton = document.getElementById("draft-invoice-button");
  const sendButton = document.getElementById("send-invoice-button");
  const empty = document.getElementById("invoice-empty");
  const render = document.getElementById("invoice-render");
  let currentInvoice = null;

  function displayDate(value) {
    if (!value) return "—";
    const date = new Date(`${value}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }
  function field(id, value) {
    const target = document.getElementById(id);
    if (target) target.textContent = value;
  }
  function renderInvoice(invoice, mode) {
    currentInvoice = invoice;
    if (empty) empty.classList.add("hidden");
    if (render) render.classList.remove("hidden");
    field("invoice-reference", invoice.reference);
    field("invoice-client-name", invoice.client_name);
    field("invoice-client-email", invoice.client_email);
    field("invoice-due-date", displayDate(invoice.due_date));
    field("invoice-description", invoice.description);
    field("invoice-subtotal", app.money(invoice.subtotal, invoice.currency));
    field("invoice-tax", `${app.money(invoice.tax_amount, invoice.currency)} (${invoice.tax_rate}%)`);
    field("invoice-total", app.money(invoice.total, invoice.currency));
    field("invoice-notes", invoice.ai_notes || "Review scope, total and due date before sending.");
    field("invoice-mode-label", `${mode || "AI"} draft`);
    const lineTarget = document.getElementById("invoice-line-items");
    if (lineTarget) {
      lineTarget.innerHTML = (invoice.line_items || []).map(function (line) {
        return `<div class="invoice-line"><div><b>${app.escapeHtml(line.name)}</b><small>${app.escapeHtml(line.description || "")}</small></div><span>${app.escapeHtml(line.quantity)}</span><span>${app.money(line.unit_price, invoice.currency)}</span><b>${app.money(line.amount, invoice.currency)}</b></div>`;
      }).join("");
    }
    const hint = document.getElementById("send-invoice-hint");
    if (hint) hint.textContent = invoice.is_demo ? "Demo mode will record a clearly labelled send." : "Ready to create and email through PayPal Invoicing.";
    if (sendButton) { sendButton.disabled = false; sendButton.textContent = invoice.status === "SENT" ? "Sent with PayPal ✓" : "Send for payment →"; }
  }

  if (form) form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const clientName = (document.getElementById("client-name").value || "").trim();
    const clientEmail = (document.getElementById("client-email").value || "").trim();
    const prompt = (document.getElementById("invoice-prompt").value || "").trim();
    app.setLoading(draftButton, true);
    try {
      const response = await app.api("/api/invoices/draft/", {
        method: "POST",
        body: JSON.stringify({ client_name: clientName, client_email: clientEmail, prompt: prompt, currency: window.PayPilot.currency || "USD" })
      });
      renderInvoice(response.invoice, response.mode);
      app.toast("Reviewable invoice draft created.", "success");
      if (response.mode !== "LLM") app.toast("The invoice is using the guided demo parser. Add an LLM key for live model drafting.");
    } catch (error) { app.toast(error.message, "error"); }
    finally { app.setLoading(draftButton, false); }
  });

  document.querySelectorAll("[data-invoice-prompt]").forEach(function (button) {
    button.addEventListener("click", function () {
      const textarea = document.getElementById("invoice-prompt");
      if (textarea) { textarea.value = button.dataset.invoicePrompt; textarea.focus(); }
    });
  });

  if (sendButton) sendButton.addEventListener("click", async function () {
    if (!currentInvoice) return;
    if (currentInvoice.status === "SENT") { app.toast("This invoice has already been marked sent."); return; }
    app.setLoading(sendButton, true);
    try {
      const response = await app.api(`/api/invoices/${encodeURIComponent(currentInvoice.id)}/send/`, { method: "POST", body: JSON.stringify({}) });
      renderInvoice(response.invoice, "PayPal");
      app.toast(response.message, "success");
    } catch (error) { app.toast(error.message, "error"); }
    finally { app.setLoading(sendButton, false); }
  });
}());
