from django.contrib import admin
from .models import ConversationMessage, InvoiceDraft, PaymentRecord, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "price", "inventory", "is_featured")
    list_filter = ("category", "is_featured")
    search_fields = ("sku", "name", "description", "tags")


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ("paypal_order_id", "status", "gross_amount", "currency", "payer_email", "is_demo", "captured_at")
    list_filter = ("status", "currency", "is_demo")
    search_fields = ("paypal_order_id", "capture_id", "payer_email")
    readonly_fields = ("raw_payload", "created_at", "updated_at")


@admin.register(InvoiceDraft)
class InvoiceDraftAdmin(admin.ModelAdmin):
    list_display = ("reference", "client_name", "total", "currency", "status", "is_demo", "created_at")
    list_filter = ("status", "currency", "is_demo")
    search_fields = ("reference", "client_name", "client_email")
    readonly_fields = ("raw_response", "created_at", "updated_at")


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ("surface", "role", "session_key", "created_at")
    list_filter = ("surface", "role")
    search_fields = ("session_key", "content")
