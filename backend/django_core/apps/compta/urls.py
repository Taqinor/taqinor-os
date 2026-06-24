from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BonCommandeFournisseurViewSet, BordereauRemiseViewSet, CaisseViewSet,
    CessionImmobilisationViewSet, CompteComptableViewSet,
    CompteTresorerieViewSet, DotationAmortissementViewSet,
    EcritureComptableViewSet, EffetViewSet, EtatsComptablesViewSet,
    ExerciceComptableViewSet, FactureFournisseurViewSet, ImmobilisationViewSet,
    JournalViewSet, LignePrevisionnelTresorerieViewSet, PeriodeComptableViewSet,
    PlanComptableViewSet, Rapprochement3VoiesViewSet, RapprochementBancaireViewSet,
    ReceptionMarchandiseViewSet, VirementInterneViewSet,
)

router = DefaultRouter()
router.register(r'plans', PlanComptableViewSet)
router.register(r'comptes', CompteComptableViewSet)
router.register(r'journaux', JournalViewSet)
router.register(r'ecritures', EcritureComptableViewSet)
router.register(r'tresorerie', CompteTresorerieViewSet)
router.register(r'periodes', PeriodeComptableViewSet)
router.register(r'exercices', ExerciceComptableViewSet)
router.register(r'immobilisations', ImmobilisationViewSet)
router.register(r'dotations', DotationAmortissementViewSet)
router.register(r'cessions', CessionImmobilisationViewSet)
router.register(r'rapprochements', RapprochementBancaireViewSet)
router.register(r'caisses', CaisseViewSet)
router.register(r'virements', VirementInterneViewSet)
router.register(r'previsionnel', LignePrevisionnelTresorerieViewSet)
router.register(r'effets', EffetViewSet)
router.register(r'bordereaux', BordereauRemiseViewSet)
router.register(r'etats', EtatsComptablesViewSet, basename='etats')
# FG131 — Rapprochement 3 voies
router.register(r'bons-commande-fournisseur', BonCommandeFournisseurViewSet)
router.register(r'receptions', ReceptionMarchandiseViewSet)
router.register(r'factures-fournisseur', FactureFournisseurViewSet)
router.register(r'rapprochements-3voies', Rapprochement3VoiesViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
