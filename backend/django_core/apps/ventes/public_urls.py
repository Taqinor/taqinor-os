from django.urls import path
from .public_views import (
    public_document, pay_page, pay_webhook,
    proposal_data, proposal_pdf, proposal_accept,
    proposal_contact_request, proposal_request_otp,
)

urlpatterns = [
    path('document/<str:token>/', public_document, name='public-document'),
    # Q6/Q7 — proposition tokenisée (données + PDF + e-signature).
    path('proposal/<str:token>/data/', proposal_data, name='public-proposal-data'),
    path('proposal/<str:token>/pdf/', proposal_pdf, name='public-proposal-pdf'),
    # QJ27 — le client demande à être contacté (notifie handler + supérieur).
    path('proposal/<str:token>/contact/', proposal_contact_request,
         name='public-proposal-contact'),
    # QJ11 — demande d'OTP (toggle ESIGN_OTP_ENABLED).
    path('proposal/<str:token>/otp/', proposal_request_otp,
         name='public-proposal-otp'),
    path('proposal/<str:token>/accept/', proposal_accept,
         name='public-proposal-accept'),
    # FG53 — page publique « Payer en ligne » + webhook (jeton PaymentLink).
    path('pay/<str:token>/', pay_page, name='public-pay-page'),
    path('pay/<str:token>/webhook/', pay_webhook, name='public-pay-webhook'),
]
