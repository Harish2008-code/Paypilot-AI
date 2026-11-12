from decimal import Decimal
import uuid

from django.db import models
from django.utils import timezone


class Product(models.Model):
    """A sellable offering that the AI shopping assistant can recommend."""

    sku = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    category = models.CharField(max_length=64)
    tags = models.CharField(max_length=240, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    inventory = models.PositiveIntegerField(default=0)
    emoji = models.CharField(max_length=8, default="✦")
    accent = models.CharField(max_length=20, default="violet")
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_featured", "name"]

    def __str__(self):
        return f"{self.sku} · {self.name}"


class PaymentRecord(models.Model):
    """A normalized local projection of an approved PayPal order/capture."""

    STATUS_CHOICES = [
        ("COMPLETED", "Completed"),
        ("PENDING", "Pending"),
        ("DECLINED", "Declined"),
        ("REFUNDED", "Refunded"),
        ("CREATED", "Created"),
    ]
    paypal_order_id = models.CharField(max_length=80, unique=True)
    capture_id = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="CREATED")
    intent = models.CharField(max_length=64, default="shop")
    currency = models.CharField(max_length=3, default="USD")
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    payer_email = models.EmailField(blank=True)
    payer_name = models.CharField(max_length=160, blank=True)
    source = models.CharField(max_length=60, default="PayPal Checkout")
    is_demo = models.BooleanField(default=False)
    raw_payload = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-captured_at", "-created_at"]

    def __str__(self):
        return f"{self.paypal_order_id} · {self.status}"


class InvoiceDraft(models.Model):
    """AI-created invoice plan, optionally materialized in PayPal Invoicing."""

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=40, unique=True, blank=True)
    client_name = models.CharField(max_length=160)
    client_email = models.EmailField()
    description = models.TextField(blank=True)
    line_items = models.JSONField(default=list)
    currency = models.CharField(max_length=3, default="USD")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    due_date = models.DateField(null=True, blank=True)
    ai_notes = models.TextField(blank=True)
    paypal_invoice_id = models.CharField(max_length=120, blank=True)
    paypal_status = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="DRAFT")
    is_demo = models.BooleanField(default=False)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PP-{timezone.now():%y%m}-{str(self.id).split('-')[0].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} · {self.client_name}"


class ConversationMessage(models.Model):
    """Auditable, minimal context history for AI-assisted commerce conversations."""

    SURFACE_CHOICES = [("SHOP", "Shop"), ("SUPPORT", "Support")]
    ROLE_CHOICES = [("USER", "User"), ("ASSISTANT", "Assistant")]
    session_key = models.CharField(max_length=64, db_index=True)
    surface = models.CharField(max_length=12, choices=SURFACE_CHOICES)
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.surface}:{self.role} · {self.content[:48]}"
