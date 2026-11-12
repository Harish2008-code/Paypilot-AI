"""Small, explicit PayPal REST client used by the Django views.

It intentionally keeps money calculations server-side. Browser code only receives a
PayPal order ID and never sees a client secret.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any
from uuid import uuid4

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
MONEY = Decimal("0.01")


class PayPalAPIError(Exception):
    """A safe error intended to be shown in the product UI."""


def money(value: Decimal | str | float) -> str:
    return str(Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP))


class PayPalService:
    timeout = 20

    @property
    def is_configured(self) -> bool:
        return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET)

    @property
    def base_url(self) -> str:
        if settings.PAYPAL_MODE == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    def public_config(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured,
            "mode": settings.PAYPAL_MODE if self.is_configured else "demo",
            "client_id": settings.PAYPAL_CLIENT_ID if self.is_configured else "",
            "currency": settings.PAYPAL_CURRENCY,
        }

    def _access_token(self) -> str:
        if not self.is_configured:
            raise PayPalAPIError("PayPal is not configured. Add Sandbox credentials to enable live API calls.")
        cache_key = f"paypal_access_token_{settings.PAYPAL_MODE}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            response = requests.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("PayPal OAuth network error: %s", exc)
            raise PayPalAPIError("Could not reach PayPal. Check the network and try again.") from exc
        if not response.ok:
            logger.warning("PayPal OAuth failed: %s", response.text[:500])
            raise PayPalAPIError("PayPal rejected the API credentials. Check your client ID and secret.")
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise PayPalAPIError("PayPal did not return an access token.")
        cache.set(cache_key, token, max(60, int(data.get("expires_in", 300)) - 60))
        return token

    def _request(self, method: str, path: str, *, payload: dict | None = None, params: dict | None = None) -> dict:
        token = self._access_token()
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Prefer": "return=representation",
                },
                json=payload,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("PayPal API network error (%s %s): %s", method, path, exc)
            raise PayPalAPIError("Could not reach PayPal. Please retry shortly.") from exc
        if not response.ok:
            try:
                details = response.json()
                reason = details.get("message") or details.get("name") or "PayPal rejected the request."
            except ValueError:
                reason = "PayPal rejected the request."
            logger.warning("PayPal API failed (%s %s): %s", method, path, response.text[:1000])
            raise PayPalAPIError(reason)
        if not response.content:
            return {}
        return response.json()

    def create_checkout_order(self, cart_items: list[dict[str, Any]]) -> dict[str, Any]:
        """Create a server-authoritative v2 Checkout order from local catalog prices."""
        if not cart_items:
            raise PayPalAPIError("Your cart is empty.")
        total = sum((Decimal(str(item["unit_price"])) * int(item["quantity"]) for item in cart_items), Decimal("0"))
        if not self.is_configured:
            return {
                "id": f"DEMO-{uuid4().hex[:18].upper()}",
                "status": "CREATED",
                "demo": True,
                "amount": money(total),
            }

        items = [
            {
                "name": item["name"][:127],
                "sku": item["sku"][:127],
                "quantity": str(int(item["quantity"])),
                "category": "DIGITAL_GOODS",
                "unit_amount": {"currency_code": settings.PAYPAL_CURRENCY, "value": money(item["unit_price"])},
            }
            for item in cart_items
        ]
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": "paypilot-cart",
                    "description": "PayPilot AI assisted purchase",
                    "items": items,
                    "amount": {
                        "currency_code": settings.PAYPAL_CURRENCY,
                        "value": money(total),
                        "breakdown": {"item_total": {"currency_code": settings.PAYPAL_CURRENCY, "value": money(total)}},
                    },
                }
            ],
            "payment_source": {"paypal": {"experience_context": {
                "brand_name": settings.PAYPAL_BUSINESS_NAME,
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
            }}},
        }
        response = self._request("POST", "/v2/checkout/orders", payload=payload)
        return {"id": response["id"], "status": response.get("status", "CREATED"), "demo": False, "raw": response}

    def capture_checkout_order(self, order_id: str) -> dict[str, Any]:
        """Capture after the payer approves in the PayPal JS SDK."""
        if order_id.startswith("DEMO-"):
            return {
                "id": order_id,
                "status": "COMPLETED",
                "demo": True,
                "purchase_units": [{"payments": {"captures": [{"id": f"CAP-{uuid4().hex[:14].upper()}", "status": "COMPLETED"}]}}],
            }
        return self._request("POST", f"/v2/checkout/orders/{order_id}/capture", payload={})

    def create_invoice(self, invoice: Any) -> dict[str, Any]:
        """Create an invoice in PayPal; the caller separately sends it after review."""
        if not self.is_configured:
            return {"id": f"DEMO-INV-{uuid4().hex[:16].upper()}", "status": "DRAFT", "demo": True}

        items = []
        for line in invoice.line_items:
            quantity = Decimal(str(line.get("quantity", 1)))
            unit_price = Decimal(str(line.get("unit_price", "0")))
            items.append({
                "name": str(line.get("name", "Professional services"))[:200],
                "description": str(line.get("description", ""))[:400],
                "quantity": str(quantity),
                "unit_amount": {"currency_code": invoice.currency, "value": money(unit_price)},
                "unit_of_measure": "ITEM",
            })
        detail: dict[str, Any] = {
            "invoice_number": invoice.reference,
            "reference": invoice.description[:100],
            "currency_code": invoice.currency,
            "invoice_date": str(date.today()),
            "payment_term": {"term_type": "DUE_ON_DATE", "due_date": str(invoice.due_date or date.today())},
        }
        payload = {
            "detail": detail,
            "invoicer": {
                "name": {"given_name": settings.PAYPAL_BUSINESS_NAME[:140]},
                "email_address": settings.PAYPAL_BUSINESS_EMAIL,
            },
            "primary_recipients": [{
                "billing_info": {"name": {"given_name": invoice.client_name[:140]}, "email_address": invoice.client_email}
            }],
            "items": items,
            "configuration": {"partial_payment": {"allow_partial_payment": False}, "allow_tip": False},
            "note": invoice.ai_notes[:4000],
        }
        return self._request("POST", "/v2/invoicing/invoices", payload=payload)

    def send_invoice(self, paypal_invoice_id: str) -> dict[str, Any]:
        if paypal_invoice_id.startswith("DEMO-INV-"):
            return {"status": "SENT", "demo": True}
        return self._request("POST", f"/v2/invoicing/invoices/{paypal_invoice_id}/send", payload={})

    def refund_capture(self, capture_id: str, amount: Decimal, currency: str) -> dict[str, Any]:
        if capture_id.startswith("CAP-"):
            return {"id": f"DEMO-RFD-{uuid4().hex[:12].upper()}", "status": "COMPLETED", "demo": True}
        return self._request(
            "POST",
            f"/v2/payments/captures/{capture_id}/refund",
            payload={"amount": {"currency_code": currency, "value": money(amount)}},
        )


paypal = PayPalService()
