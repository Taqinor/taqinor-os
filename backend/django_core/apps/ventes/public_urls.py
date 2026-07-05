from django.urls import path
from .public_views import (
    public_document, public_bcf_document, pay_page, pay_webhook,
    proposal_data, proposal_pdf, proposal_accept,
    proposal_contact_request, proposal_request_otp,
    ecatalogue_public, ecatalogue_demander_devis,
)

urlpatterns = [
    path('document/<str:token>/', public_document, name='public-document'),
    # QS3 — PDF tokenisé du bon de commande FOURNISSEUR (destiné au fournisseur).
    path('bcf/<str:token>/', public_bcf_document, name='public-bcf-document'),
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
    # XPOS14 — e-catalogue public (lecture) + panier « Demander un devis ».
    path('ecatalogue/<str:token>/', ecatalogue_public,
         name='public-ecatalogue'),
    path('ecatalogue/<str:token>/demander-devis/', ecatalogue_demander_devis,
         name='public-ecatalogue-demander-devis'),
]
