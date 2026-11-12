import json
from decimal import Decimal

from django.test import TestCase, override_settings

from .models import PaymentRecord
from .services.demo import ensure_catalog


@override_settings(PAYPAL_CLIENT_ID="", PAYPAL_CLIENT_SECRET="", OPENAI_API_KEY="")
class CommerceFlowTests(TestCase):
    """Regression tests for the zero-key guided walkthrough and human-control boundary."""

    def setUp(self):
        ensure_catalog()

    def post_json(self, path, data):
        return self.client.post(path, json.dumps(data), content_type="application/json")

    def test_primary_pages_render(self):
        for path in ("/", "/shop/", "/invoices/", "/support/", "/analytics/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)

    def test_demo_checkout_calculates_server_cart_and_records_capture(self):
        added = self.post_json("/api/cart/add/", {"sku": "BRAND-SPRINT", "quantity": 1})
        self.assertEqual(added.status_code, 200)
        self.assertEqual(added.json()["cart"]["total"], "89.00")

        order = self.post_json("/api/checkout/create/", {}).json()
        self.assertTrue(order["demo"])
        captured = self.post_json("/api/checkout/capture/", {"order_id": order["id"]})
        self.assertEqual(captured.status_code, 200)
        self.assertEqual(captured.json()["payment"]["status"], "COMPLETED")
        self.assertTrue(PaymentRecord.objects.get(paypal_order_id=order["id"]).is_demo)

    def test_invoice_draft_and_explicit_refund_gate(self):
        invoice = self.post_json("/api/invoices/draft/", {
            "client_name": "Acme Labs",
            "client_email": "billing@acme.example.com",
            "prompt": "Invoice $1200 for a product strategy sprint, due in 14 days.",
            "currency": "USD",
        })
        self.assertEqual(invoice.status_code, 200)
        self.assertEqual(invoice.json()["invoice"]["total"], "1200.00")

        payment = PaymentRecord.objects.create(
            paypal_order_id="DEMO-TEST-CAPTURE", capture_id="CAP-TEST-CAPTURE",
            status="COMPLETED", gross_amount=Decimal("12.00"), currency="USD", is_demo=True,
        )
        blocked = self.post_json(f"/api/payments/{payment.id}/refund/", {"amount": "12.00"})
        self.assertEqual(blocked.status_code, 403)
        approved = self.post_json(f"/api/payments/{payment.id}/refund/", {"operator_confirmation": "REFUND", "amount": "12.00"})
        self.assertEqual(approved.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "REFUNDED")

    def test_ai_shop_response_is_catalog_grounded(self):
        response = self.post_json("/api/assistant/chat/", {"message": "I need a launch plan under $100"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "guided demo")
        self.assertTrue(payload["suggested_skus"])
        self.assertIn("BRAND-SPRINT", payload["suggested_skus"])
