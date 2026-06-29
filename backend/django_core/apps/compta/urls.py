from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BaremeIndemniteViewSet, BordereauRemiseViewSet, CaisseViewSet,
    CessionImmobilisationViewSet, CompteComptableViewSet,
    CompteTresorerieViewSet, DeclarationTVAViewSet, DotationAmortissementViewSet,
    EcritureComptableViewSet, EffetViewSet, EtatsComptablesViewSet,
    ExerciceComptableViewSet, ImmobilisationViewSet, IndemniteChantierViewSet,
    JournalViewSet, LignePrevisionnelTresorerieViewSet, NoteFraisViewSet,
    PaymentRunViewSet, PeriodeComptableViewSet, PlanComptableViewSet,
    RapprochementBancaireViewSet, RapprochementViewSet, RetenueSourceViewSet,
    VirementInterneViewSet,
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
router.register(r'rapprochements-3voies', RapprochementViewSet,
                basename='rapprochement-3voies')
router.register(r'caisses', CaisseViewSet)
router.register(r'virements', VirementInterneViewSet)
router.register(r'previsionnel', LignePrevisionnelTresorerieViewSet)
router.register(r'effets', EffetViewSet)
router.register(r'bordereaux', BordereauRemiseViewSet)
router.register(r'payment-runs', PaymentRunViewSet)
router.register(r'notes-frais', NoteFraisViewSet)
router.register(r'baremes-indemnite', BaremeIndemniteViewSet)
router.register(r'indemnites-chantier', IndemniteChantierViewSet)
router.register(r'declarations-tva', DeclarationTVAViewSet)
router.register(r'retenues-source', RetenueSourceViewSet)
router.register(r'etats', EtatsComptablesViewSet, basename='etats')

urlpatterns = [
    path('', include(router.urls)),
]
