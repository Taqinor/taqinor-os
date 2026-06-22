from django.urls import path
from .public_views import public_document, pay_page, pay_webhook

urlpatterns = [
    path('document/<str:token>/', public_document, name='public-document'),
    # FG53 — page publique « Payer en ligne » + webhook (jeton PaymentLink).
    path('pay/<str:token>/', pay_page, name='public-pay-page'),
    path('pay/<str:token>/webhook/', pay_webhook, name='public-pay-webhook'),
]
