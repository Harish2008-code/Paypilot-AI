"""Clearly labelled demo catalog/data used for a zero-key local walkthrough."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from commerce.models import InvoiceDraft, PaymentRecord, Product

CATALOG = [
    {
        "sku": "BRAND-SPRINT", "name": "Brand Sprint Kit", "category": "Strategy",
        "description": "A guided 90-minute positioning session with a clear messaging map and next-step brief.",
        "tags": "brand strategy positioning workshop messaging founder", "price": Decimal("89.00"), "inventory": 18,
        "emoji": "✦", "accent": "violet", "is_featured": True,
    },
    {
        "sku": "COPY-LAB", "name": "Launch Copy Lab", "category": "Marketing",
        "description": "Conversion-focused homepage and launch-email review with annotated, reusable copy prompts.",
        "tags": "copywriting launch email marketing conversion website", "price": Decimal("59.00"), "inventory": 31,
        "emoji": "✎", "accent": "coral", "is_featured": True,
    },
    {
        "sku": "FLOW-AUTO", "name": "Workflow Automator", "category": "Automation",
        "description": "A practical automation map for client intake, handoffs, reminders and weekly reporting.",
        "tags": "automation operations workflow ai integrations productivity", "price": Decimal("149.00"), "inventory": 12,
        "emoji": "↗", "accent": "teal", "is_featured": True,
    },
    {
        "sku": "DISCOVERY", "name": "Discovery Workshop", "category": "Strategy",
        "description": "Live collaborative workshop to prioritize an offer, audience, roadmap and measurable outcome.",
        "tags": "consulting discovery workshop roadmap strategy team", "price": Decimal("240.00"), "inventory": 8,
        "emoji": "◌", "accent": "amber", "is_featured": False,
    },
    {
        "sku": "CREATOR-OS", "name": "Creator OS", "category": "Systems",
        "description": "A modular Notion-style operating system for content planning, client work and weekly reviews.",
        "tags": "creator content systems notion templates productivity", "price": Decimal("119.00"), "inventory": 22,
        "emoji": "▦", "accent": "blue", "is_featured": False,
    },
    {
        "sku": "CARE-PLAN", "name": "Launch Care Plan", "category": "Support",
        "description": "Seven days of async launch support with priority answers, QA checklists and performance notes.",
        "tags": "support launch qa customer success care plan", "price": Decimal("39.00"), "inventory": 45,
        "emoji": "♡", "accent": "pink", "is_featured": False,
    },
]


def ensure_catalog() -> int:
    """Seed only missing SKUs; never overwrite a merchant's edited catalog."""
    created = 0
    for row in CATALOG:
        _, was_created = Product.objects.get_or_create(sku=row["sku"], defaults=row)
        created += int(was_created)
    return created


def seed_demo_data() -> dict[str, int]:
    ensure_catalog()
    now = timezone.now()
    rows = [
        ("DEMO-ORD-9X1A", "CAP-DEMO-9X1A", "COMPLETED", "149.00", "maya@example.com", "Maya Patel", "Workflow Automator", 1),
        ("DEMO-ORD-7K2B", "CAP-DEMO-7K2B", "COMPLETED", "89.00", "leon@example.com", "Leon Wu", "Brand Sprint Kit", 2),
        ("DEMO-ORD-5P3C", "CAP-DEMO-5P3C", "COMPLETED", "59.00", "ava@example.com", "Ava Smith", "Launch Copy Lab", 4),
        ("DEMO-ORD-3N4D", "", "PENDING", "119.00", "sam@example.com", "Sam Rivera", "Creator OS", 0),
        ("DEMO-ORD-1M5E", "CAP-DEMO-1M5E", "REFUNDED", "39.00", "taylor@example.com", "Taylor Brooks", "Launch Care Plan", 8),
    ]
    payment_count = 0
    for order_id, capture_id, status, amount, email, name, product, days_ago in rows:
        _, created = PaymentRecord.objects.update_or_create(
            paypal_order_id=order_id,
            defaults={
                "capture_id": capture_id,
                "status": status,
                "currency": "USD",
                "gross_amount": Decimal(amount),
                "payer_email": email,
                "payer_name": name,
                "source": "PayPal Checkout · demo data",
                "is_demo": True,
                "raw_payload": {"demo": True, "product": product},
                "captured_at": now - timedelta(days=days_ago) if status != "PENDING" else None,
            },
        )
        payment_count += int(created)

    invoice, created = InvoiceDraft.objects.get_or_create(
        reference="PP-DEMO-INV-01",
        defaults={
            "client_name": "Acme Labs", "client_email": "billing@acme.example.com",
            "description": "Product strategy and launch planning", "currency": "USD",
            "line_items": [{"name": "Product strategy sprint", "description": "Workshop and decision memo", "quantity": "1", "unit_price": "980.00", "amount": "980.00"}],
            "subtotal": Decimal("980.00"), "tax_rate": Decimal("0.00"), "tax_amount": Decimal("0.00"), "total": Decimal("980.00"),
            "due_date": timezone.localdate() + timedelta(days=10), "ai_notes": "Demo invoice; verify scope and due date before sending.",
            "status": "DRAFT", "is_demo": True,
        },
    )
    return {"products": Product.objects.count(), "payments_created": payment_count, "invoice_created": int(created)}
