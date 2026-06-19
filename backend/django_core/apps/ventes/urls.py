from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DevisViewSet,
    LigneDevisViewSet,
    BonCommandeViewSet,
    FactureViewSet,
    LigneFactureViewSet,
    PaiementViewSet,
    AvoirViewSet,
)
from .recouvrement import (
    FollowupLevelViewSet,
    relances_list,
    balance_agee,
    client_releve,
    client_releve_pdf,
    lettre_relance_pdf,
)
from .journal_view import journal_ventes
from .numbering_view import numerotation_audit
from .extra_docs_views import lettre_relance_premium, fiche_remise_premium

router = DefaultRouter()
router.register(r'devis', DevisViewSet)
router.register(r'devis-lignes', LigneDevisViewSet)
router.register(r'bons-commande', BonCommandeViewSet)
router.register(r'factures', FactureViewSet)
router.register(r'factures-lignes', LigneFactureViewSet)
router.register(r'paiements', PaiementViewSet)
router.register(r'avoirs', AvoirViewSet)
router.register(r'niveaux-relance', FollowupLevelViewSet,
                basename='niveau-relance')

urlpatterns = [
    # Export comptable : journal des ventes + résumé TVA (.xlsx).
    path('journal-ventes/', journal_ventes, name='journal-ventes'),
    # Audit de la numérotation séquentielle (trous/doublons) — admin.
    path('numerotation-audit/', numerotation_audit, name='numerotation-audit'),
    # Recouvrement (vue/consigne/impression — jamais d'envoi).
    path('relances/', relances_list, name='relances-list'),
    path('balance-agee/', balance_agee, name='balance-agee'),
    path('clients/<int:client_id>/releve/', client_releve, name='client-releve'),
    path('clients/<int:client_id>/releve-pdf/', client_releve_pdf,
         name='client-releve-pdf'),
    path('factures/<int:facture_id>/lettre-relance-pdf/', lettre_relance_pdf,
         name='lettre-relance-pdf'),
    # Documents premium ADDITIFS (langage visuel du devis) — rendus à la volée.
    # Lettre de relance premium niveau 1/2/3 (?niveau=) et fiche de remise.
    path('factures/<int:facture_id>/lettre-relance-premium/',
         lettre_relance_premium, name='lettre-relance-premium'),
    path('chantiers/<int:chantier_id>/fiche-remise-premium/',
         fiche_remise_premium, name='fiche-remise-premium'),
    path('', include(router.urls)),
]
