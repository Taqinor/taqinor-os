"""Routes du module Facturation (``apps.facturation``) — ODX18.

Nouveau préfixe ``/api/django/facturation/…``. Les mêmes ViewSets et vues de
recouvrement sont AUSSI servis par ``apps.ventes.urls`` sous
``/api/django/ventes/…`` (routes historiques conservées à l'identique pour ne
casser aucun client). Les ViewSets gardent le scoping ``request.user.company`` +
l'assignation forcée de ``company`` (hérité de ``TenantMixin``).

Basenames et noms d'URL explicitement préfixés ``fac-``/``facturation-`` pour NE
PAS entrer en collision avec les noms d'URL du routeur ventes (qui reverse
``facture-list``, ``relances-list`` etc.).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AvoirViewSet,
    FactureViewSet,
    FollowupLevelViewSet,
    LigneFactureViewSet,
    NoteDebitViewSet,
    PaiementViewSet,
)
from apps.ventes.recouvrement import (
    balance_agee,
    client_releve,
    client_releve_pdf,
    lettre_relance_pdf,
    relances_list,
)

router = DefaultRouter()
router.register(r'factures', FactureViewSet, basename='fac-facture')
router.register(r'factures-lignes', LigneFactureViewSet,
                basename='fac-ligne-facture')
router.register(r'paiements', PaiementViewSet, basename='fac-paiement')
router.register(r'avoirs', AvoirViewSet, basename='fac-avoir')
router.register(r'notes-debit', NoteDebitViewSet, basename='fac-note-debit')
router.register(r'niveaux-relance', FollowupLevelViewSet,
                basename='fac-niveau-relance')

urlpatterns = [
    # Recouvrement (vue/consigne/impression — jamais d'envoi). Mêmes vues que le
    # mount ventes/, sous des noms d'URL préfixés pour éviter toute collision de
    # reverse().
    path('relances/', relances_list, name='facturation-relances-list'),
    path('balance-agee/', balance_agee, name='facturation-balance-agee'),
    path('clients/<int:client_id>/releve/', client_releve,
         name='facturation-client-releve'),
    path('clients/<int:client_id>/releve-pdf/', client_releve_pdf,
         name='facturation-client-releve-pdf'),
    path('factures/<int:facture_id>/lettre-relance-pdf/', lettre_relance_pdf,
         name='facturation-lettre-relance-pdf'),
    path('', include(router.urls)),
]
