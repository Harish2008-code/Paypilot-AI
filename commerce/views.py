from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Sum
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import ConversationMessage, InvoiceDraft, PaymentRecord, Product
from .services.ai import ai, decimal_money
from .services.demo import ensure_catalog
from .services.paypal import PayPalAPIError, paypal


def _session_key(request: HttpRequest) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _body(request: HttpRequest) -> dict[str, Any]:
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def _cart_state(request: HttpRequest) -> dict[str, int]:
    raw = request.session.get("cart", {})
    if not isinstance(raw, dict):
        return {}
    state: dict[str, int] = {}
    for sku, qty in raw.items():
        try:
            value = int(qty)
        except (ValueError, TypeError):
            continue
        if value > 0:
            state[str(sku)] = min(value, 10)
    return state


def _cart_from_state(state: dict[str, int]) -> dict[str, Any]:
    products = Product.objects.filter(sku__in=state.keys())
    by_sku = {product.sku: product for product in products}
    items = []
    for sku, quantity in state.items():
        product = by_sku.get(sku)
        if not product or product.inventory < 1:
            continue
        quantity = min(quantity, product.inventory, 10)
        amount = product.price * quantity
        items.append({
            "sku": product.sku,
            "name": product.name,
            "emoji": product.emoji,
            "quantity": quantity,
            "unit_price": str(product.price),
            "amount": str(amount),
        })
    total = sum((Decimal(item["amount"]) for item in items), Decimal("0.00"))
    return {
        "items": items,
        "count": sum(item["quantity"] for item in items),
        "total": str(total.quantize(Decimal("0.01"))),
        "currency": settings.PAYPAL_CURRENCY,
    }


def _cart(request: HttpRequest) -> dict[str, Any]:
    return _cart_from_state(_cart_state(request))


def _set_cart(request: HttpRequest, cart_state: dict[str, int]) -> dict[str, Any]:
    request.session["cart"] = cart_state
    request.session.modified = True
    return _cart(request)


def _format_payment(payment: PaymentRecord) -> dict[str, Any]:
    timestamp = payment.captured_at or payment.created_at
    return {
        "id": payment.pk,
        "order_id": payment.paypal_order_id,
        "capture_id": payment.capture_id,
        "status": payment.status,
        "amount": f"{payment.gross_amount:.2f}",
        "currency": payment.currency,
        "payer_email": payment.payer_email,
        "payer_name": payment.payer_name,
        "source": payment.source,
        "is_demo": payment.is_demo,
        "timestamp": timezone.localtime(timestamp).strftime("%d %b · %H:%M"),
        "iso_timestamp": timestamp.isoformat(),
    }


def _format_invoice(invoice: InvoiceDraft) -> dict[str, Any]:
    return {
        "id": str(invoice.id),
        "reference": invoice.reference,
        "client_name": invoice.client_name,
        "client_email": invoice.client_email,
        "description": invoice.description,
        "line_items": invoice.line_items,
        "currency": invoice.currency,
        "subtotal": f"{invoice.subtotal:.2f}",
        "tax_rate": f"{invoice.tax_rate:.2f}",
        "tax_amount": f"{invoice.tax_amount:.2f}",
        "total": f"{invoice.total:.2f}",
        "due_date": invoice.due_date.isoformat() if invoice.due_date else "",
        "ai_notes": invoice.ai_notes,
        "paypal_invoice_id": invoice.paypal_invoice_id,
        "status": invoice.status,
        "is_demo": invoice.is_demo,
    }


def _metrics() -> dict[str, Any]:
    records = list(PaymentRecord.objects.all())
    completed = [record for record in records if record.status == "COMPLETED"]
    attempts = [record for record in records if record.status not in {"CREATED"}]
    gross = sum((record.gross_amount for record in completed), Decimal("0.00"))
    success_rate = int((len(completed) / len(attempts) * 100) if attempts else 0)
    open_invoices = InvoiceDraft.objects.filter(status__in=["DRAFT", "SENT"]).aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    return {
        "gross": gross,
        "completed": len(completed),
        "success_rate": success_rate,
        "open_invoices": open_invoices,
        "records": records,
    }


def _common_context(request: HttpRequest, section: str) -> dict[str, Any]:
    ensure_catalog()
    return {
        "section": section,
        "cart": _cart(request),
        "paypal_config": paypal.public_config(),
        "ai_mode": ai.mode,
    }


@require_GET
def dashboard(request: HttpRequest):
    context = _common_context(request, "dashboard")
    metrics = _metrics()
    invoices_qs = InvoiceDraft.objects.all()
    brief = ai.operations_brief(metrics["records"], invoices_qs[:12])
    forecast = ai.forecast(metrics["records"])
    context.update({
        "metrics": metrics,
        "brief": brief,
        "forecast": forecast,
        "recent_payments": [_format_payment(p) for p in PaymentRecord.objects.all()[:6]],
        "recent_invoices": invoices_qs[:4],
        "status_counts": PaymentRecord.objects.values("status").annotate(count=Count("id")),
    })
    return render(request, "commerce/dashboard.html", context)


@require_GET
def shop(request: HttpRequest):
    context = _common_context(request, "shop")
    context.update({
        "products": Product.objects.all(),
        "catalog_json": [
            {"sku": p.sku, "name": p.name, "price": str(p.price), "emoji": p.emoji, "category": p.category}
            for p in Product.objects.all()
        ],
    })
    return render(request, "commerce/shop.html", context)


@require_GET
def invoices(request: HttpRequest):
    context = _common_context(request, "invoices")
    context["invoice_list"] = InvoiceDraft.objects.all()[:8]
    return render(request, "commerce/invoices.html", context)


@require_GET
def support(request: HttpRequest):
    context = _common_context(request, "support")
    context["payments"] = [_format_payment(payment) for payment in PaymentRecord.objects.all()[:15]]
    return render(request, "commerce/support.html", context)


@require_GET
def analytics(request: HttpRequest):
    context = _common_context(request, "analytics")
    metrics = _metrics()
    context.update({
        "metrics": metrics,
        "forecast": ai.forecast(metrics["records"]),
        "payments": [_format_payment(payment) for payment in PaymentRecord.objects.all()[:25]],
        "status_counts": {row["status"]: row["count"] for row in PaymentRecord.objects.values("status").annotate(count=Count("id"))},
    })
    return render(request, "commerce/analytics.html", context)


@require_GET
def cart_detail(request: HttpRequest):
    ensure_catalog()
    return JsonResponse({"ok": True, "cart": _cart(request)})


@require_POST
def cart_add(request: HttpRequest):
    ensure_catalog()
    data = _body(request)
    sku = str(data.get("sku", "")).strip()
    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return _error("Choose a valid quantity.")
    product = Product.objects.filter(sku=sku).first()
    if not product:
        return _error("That product is no longer available.", 404)
    if product.inventory < 1:
        return _error("That product is currently out of stock.")
    state = _cart_state(request)
    state[sku] = min(max(quantity, 1) + state.get(sku, 0), min(product.inventory, 10))
    return JsonResponse({"ok": True, "cart": _set_cart(request, state), "message": f"{product.name} added to your cart."})


@require_POST
def cart_update(request: HttpRequest):
    ensure_catalog()
    data = _body(request)
    sku = str(data.get("sku", "")).strip()
    try:
        quantity = int(data.get("quantity", 0))
    except (TypeError, ValueError):
        return _error("Choose a valid quantity.")
    state = _cart_state(request)
    product = Product.objects.filter(sku=sku).first()
    if quantity <= 0 or not product:
        state.pop(sku, None)
    else:
        state[sku] = min(quantity, product.inventory, 10)
    return JsonResponse({"ok": True, "cart": _set_cart(request, state)})


@require_POST
def assistant_chat(request: HttpRequest):
    ensure_catalog()
    data = _body(request)
    message = str(data.get("message", "")).strip()
    if not message:
        return _error("Write a question for the shopping copilot.")
    if len(message) > 1200:
        return _error("Keep your question under 1,200 characters.")
    session_key = _session_key(request)
    ConversationMessage.objects.create(session_key=session_key, surface="SHOP", role="USER", content=message)
    result = ai.shopping_reply(message, Product.objects.all(), _cart(request)["items"])
    ConversationMessage.objects.create(
        session_key=session_key, surface="SHOP", role="ASSISTANT", content=result["reply"],
        metadata={"suggested_skus": result["suggested_skus"], "mode": result["mode"]},
    )
    return JsonResponse({"ok": True, **result})


@require_POST
def checkout_create(request: HttpRequest):
    ensure_catalog()
    cart = _cart(request)
    if not cart["items"]:
        return _error("Add an item before starting checkout.")
    try:
        order = paypal.create_checkout_order(cart["items"])
    except PayPalAPIError as exc:
        return _error(str(exc), 502)
    pending = request.session.get("pending_orders", {})
    if not isinstance(pending, dict):
        pending = {}
    pending[order["id"]] = {"items": cart["items"], "total": cart["total"], "currency": cart["currency"]}
    request.session["pending_orders"] = pending
    request.session.modified = True
    return JsonResponse({"ok": True, **order})


def _capture_details(response: dict[str, Any], fallback_total: str, currency: str) -> tuple[str, str, str, str, str]:
    status = str(response.get("status", "COMPLETED"))
    capture_id = ""
    amount = fallback_total
    response_currency = currency
    payer = response.get("payer", {}) if isinstance(response.get("payer"), dict) else {}
    email = str(payer.get("email_address", ""))
    name_data = payer.get("name", {}) if isinstance(payer.get("name"), dict) else {}
    name = str(name_data.get("given_name", "") + " " + name_data.get("surname", "")).strip()
    units = response.get("purchase_units", [])
    if units and isinstance(units[0], dict):
        captures = units[0].get("payments", {}).get("captures", [])
        if captures and isinstance(captures[0], dict):
            capture = captures[0]
            capture_id = str(capture.get("id", ""))
            status = str(capture.get("status", status))
            amount_data = capture.get("amount", {})
            if isinstance(amount_data, dict):
                amount = str(amount_data.get("value", amount))
                response_currency = str(amount_data.get("currency_code", response_currency))
    return status, capture_id, amount, response_currency, f"{email}|{name}"


@require_POST
def checkout_capture(request: HttpRequest):
    data = _body(request)
    order_id = str(data.get("order_id", "")).strip()
    pending = request.session.get("pending_orders", {})
    if not order_id or not isinstance(pending, dict) or order_id not in pending:
        return _error("This checkout session is not recognized. Start checkout again.", 403)
    snapshot = pending[order_id]
    try:
        response = paypal.capture_checkout_order(order_id)
    except PayPalAPIError as exc:
        return _error(str(exc), 502)
    status, capture_id, amount, currency, payer = _capture_details(response, snapshot["total"], snapshot["currency"])
    email, _, payer_name = payer.partition("|")
    payment, _ = PaymentRecord.objects.update_or_create(
        paypal_order_id=order_id,
        defaults={
            "capture_id": capture_id,
            "status": status if status in dict(PaymentRecord.STATUS_CHOICES) else "CREATED",
            "intent": "AI assisted storefront",
            "currency": currency,
            "gross_amount": decimal_money(amount),
            "payer_email": email,
            "payer_name": payer_name,
            "source": "PayPal Checkout" if not response.get("demo") else "PayPal Checkout · guided demo",
            "is_demo": bool(response.get("demo", False)),
            "raw_payload": response,
            "captured_at": timezone.now() if status == "COMPLETED" else None,
        },
    )
    pending.pop(order_id, None)
    request.session["pending_orders"] = pending
    if status == "COMPLETED":
        request.session["cart"] = {}
    request.session.modified = True
    return JsonResponse({
        "ok": True,
        "payment": _format_payment(payment),
        "message": "Payment captured and recorded." if status == "COMPLETED" else f"PayPal returned {status}; review the order before fulfilment.",
    })


@require_POST
def invoice_draft(request: HttpRequest):
    data = _body(request)
    prompt = str(data.get("prompt", "")).strip()
    client_name = str(data.get("client_name", "")).strip()
    client_email = str(data.get("client_email", "")).strip()
    currency = str(data.get("currency", settings.PAYPAL_CURRENCY)).upper()[:3]
    if len(prompt) < 8:
        return _error("Give the invoice copilot a little more context about the work and amount.")
    if not client_name:
        return _error("Add the client name before drafting the invoice.")
    try:
        validate_email(client_email)
    except ValidationError:
        return _error("Enter a valid client email before drafting the invoice.")
    plan = ai.invoice_plan(prompt, client_name, client_email, currency)
    try:
        due_date = datetime.fromisoformat(plan["due_date"]).date()
    except (KeyError, TypeError, ValueError):
        due_date = timezone.localdate()
    invoice = InvoiceDraft.objects.create(
        client_name=client_name,
        client_email=client_email,
        description=plan["description"],
        line_items=plan["line_items"],
        currency=currency,
        subtotal=decimal_money(plan["subtotal"]),
        tax_rate=decimal_money(plan["tax_rate"]),
        tax_amount=decimal_money(plan["tax_amount"]),
        total=decimal_money(plan["total"]),
        due_date=due_date,
        ai_notes=plan["ai_notes"],
        is_demo=not paypal.is_configured,
        raw_response={"ai_mode": plan["mode"], "plan": plan},
    )
    return JsonResponse({"ok": True, "invoice": _format_invoice(invoice), "mode": plan["mode"]})


@require_POST
def invoice_send(request: HttpRequest, invoice_id):
    invoice = get_object_or_404(InvoiceDraft, pk=invoice_id)
    try:
        if not invoice.paypal_invoice_id:
            created = paypal.create_invoice(invoice)
            invoice.paypal_invoice_id = str(created.get("id", ""))
            invoice.paypal_status = str(created.get("status", "DRAFT"))
            invoice.is_demo = bool(created.get("demo", False))
            invoice.raw_response = {**invoice.raw_response, "paypal_create": created}
            invoice.save(update_fields=["paypal_invoice_id", "paypal_status", "is_demo", "raw_response", "updated_at"])
        sent = paypal.send_invoice(invoice.paypal_invoice_id)
    except PayPalAPIError as exc:
        return _error(str(exc), 502)
    invoice.status = "SENT"
    invoice.paypal_status = str(sent.get("status", "SENT"))
    invoice.raw_response = {**invoice.raw_response, "paypal_send": sent}
    invoice.save(update_fields=["status", "paypal_status", "raw_response", "updated_at"])
    return JsonResponse({
        "ok": True,
        "invoice": _format_invoice(invoice),
        "message": "Demo invoice marked as sent." if invoice.is_demo else "Invoice created and sent with PayPal Invoicing.",
    })


@require_POST
def support_chat(request: HttpRequest):
    data = _body(request)
    message = str(data.get("message", "")).strip()
    payment_id = data.get("payment_id")
    if not message:
        return _error("Enter the customer’s question or issue.")
    payment = None
    if payment_id:
        try:
            payment = PaymentRecord.objects.filter(pk=int(payment_id)).first()
        except (TypeError, ValueError):
            return _error("Choose a valid order.")
    session_key = _session_key(request)
    ConversationMessage.objects.create(session_key=session_key, surface="SUPPORT", role="USER", content=message, metadata={"payment_id": payment_id})
    result = ai.support_reply(message, payment)
    ConversationMessage.objects.create(session_key=session_key, surface="SUPPORT", role="ASSISTANT", content=result["reply"], metadata={"payment_id": payment_id, "mode": result["mode"]})
    return JsonResponse({"ok": True, **result})


@require_POST
def payment_refund(request: HttpRequest, payment_id: int):
    """A deliberately explicit operator action; AI can recommend but never invokes this endpoint itself."""
    data = _body(request)
    if data.get("operator_confirmation") != "REFUND":
        return _error("Type the explicit operator confirmation before creating a refund.", 403)
    payment = get_object_or_404(PaymentRecord, pk=payment_id)
    if payment.status != "COMPLETED":
        return _error("Only completed payments can be refunded.")
    amount = decimal_money(data.get("amount", payment.gross_amount), Decimal("-1"))
    if amount <= 0 or amount > payment.gross_amount:
        return _error("Enter a refund amount up to the captured amount.")
    if not payment.capture_id:
        return _error("No capture ID is available for this payment.")
    try:
        result = paypal.refund_capture(payment.capture_id, amount, payment.currency)
    except PayPalAPIError as exc:
        return _error(str(exc), 502)
    if result.get("status") == "COMPLETED":
        payment.status = "REFUNDED"
        payment.raw_payload = {**payment.raw_payload, "refund": result}
        payment.save(update_fields=["status", "raw_payload", "updated_at"])
    return JsonResponse({"ok": True, "payment": _format_payment(payment), "message": "Refund submitted to PayPal for review and processing."})


@require_POST
def analytics_refresh(request: HttpRequest):
    metrics = _metrics()
    return JsonResponse({
        "ok": True,
        "brief": ai.operations_brief(metrics["records"], InvoiceDraft.objects.all()[:12]),
        "forecast": ai.forecast(metrics["records"]),
        "metrics": {
            "gross": f"{metrics['gross']:.2f}",
            "completed": metrics["completed"],
            "success_rate": metrics["success_rate"],
            "open_invoices": f"{metrics['open_invoices']:.2f}",
        },
    })
