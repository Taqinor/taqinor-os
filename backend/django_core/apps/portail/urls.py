"""Routes du module Portail client (``apps.portail``) — ODX12.

Nouveau préfixe ``/api/django/portail/…``. Les mêmes ViewSets sont AUSSI servis
par ``apps.compta.urls`` sous ``/api/django/compta/…`` (routes historiques
conservées à l'identique pour ne casser aucun client, y compris les vues
publiques tokenisées ``portail/<token>/…`` qui restent servies par compta). Les
ViewSets gardent le scoping ``request.user.company`` + l'assignation forcée de
``company`` (hérité de ``_ComptaBaseViewSet`` = ``TenantMixin``).

Basenames explicitement préfixés ``portail-…`` pour NE PAS entrer en collision
avec les noms d'URL du routeur compta.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcceptationDevisPortailViewSet,
    ComptePortailClientViewSet,
    DemandeTicketPortailViewSet,
    DocumentClientPortailViewSet,
    JalonChantierPortailViewSet,
    PaiementFacturePortailViewSet,
)

router = DefaultRouter()
router.register(r'comptes-portail', ComptePortailClientViewSet,
                basename='portail-compte')
router.register(r'acceptations-devis-portail', AcceptationDevisPortailViewSet,
                basename='portail-acceptation-devis')
router.register(r'paiements-facture-portail', PaiementFacturePortailViewSet,
                basename='portail-paiement-facture')
router.register(r'documents-client-portail', DocumentClientPortailViewSet,
                basename='portail-document-client')
router.register(r'jalons-chantier-portail', JalonChantierPortailViewSet,
                basename='portail-jalon-chantier')
router.register(r'demandes-ticket-portail', DemandeTicketPortailViewSet,
                basename='portail-demande-ticket')

urlpatterns = [
    path('', include(router.urls)),
]
