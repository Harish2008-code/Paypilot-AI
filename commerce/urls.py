from django.urls import path
from . import views

app_name = "commerce"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("shop/", views.shop, name="shop"),
    path("invoices/", views.invoices, name="invoices"),
    path("support/", views.support, name="support"),
    path("analytics/", views.analytics, name="analytics"),
    path("api/cart/", views.cart_detail, name="cart_detail"),
    path("api/cart/add/", views.cart_add, name="cart_add"),
    path("api/cart/update/", views.cart_update, name="cart_update"),
    path("api/assistant/chat/", views.assistant_chat, name="assistant_chat"),
    path("api/checkout/create/", views.checkout_create, name="checkout_create"),
    path("api/checkout/capture/", views.checkout_capture, name="checkout_capture"),
    path("api/invoices/draft/", views.invoice_draft, name="invoice_draft"),
    path("api/invoices/<uuid:invoice_id>/send/", views.invoice_send, name="invoice_send"),
    path("api/support/chat/", views.support_chat, name="support_chat"),
    path("api/payments/<int:payment_id>/refund/", views.payment_refund, name="payment_refund"),
    path("api/analytics/refresh/", views.analytics_refresh, name="analytics_refresh"),
]
