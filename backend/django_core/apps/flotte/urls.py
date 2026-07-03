from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccuseCharteViewSet,
    ActifFlotteViewSet,
    AffectationConducteurViewSet,
    AssuranceVehiculeViewSet,
    BaremeVignetteViewSet,
    BudgetFlotteViewSet,
    CarteCarburantViewSet,
    CarteGriseVehiculeViewSet,
    CharteVehiculeViewSet,
    ConducteurViewSet,
    ContratVehiculeViewSet,
    CoutVehiculeViewSet,
    DemandeVehiculeViewSet,
    EcheanceEntretienViewSet,
    EcheanceReglementaireViewSet,
    EnginRoulantViewSet,
    EtatDesLieuxViewSet,
    GarageViewSet,
    GarantieFlotteViewSet,
    InfractionViewSet,
    InspectionVehiculeViewSet,
    ModeleInspectionViewSet,
    ModeleVehiculeViewSet,
    OrdreReparationViewSet,
    PieceFlotteViewSet,
    PlanEntretienViewSet,
    PneumatiqueViewSet,
    PleinCarburantViewSet,
    ReferentielFlotteViewSet,
    ReleveTelematiqueViewSet,
    ReservationVehiculeViewSet,
    SignalementVehiculeViewSet,
    SinistreViewSet,
    TrajetChantierViewSet,
    TrajetTelematiqueViewSet,
    VehiculeViewSet,
    VisiteTechniqueViewSet,
    rapport_budget,
    rapport_couts,
    rapport_remplacement,
)

router = DefaultRouter()
router.register(r'vehicules', VehiculeViewSet)
router.register(r'modeles-vehicule', ModeleVehiculeViewSet)
router.register(r'engins', EnginRoulantViewSet)
router.register(r'referentiels', ReferentielFlotteViewSet)
router.register(r'actifs', ActifFlotteViewSet)
router.register(r'conducteurs', ConducteurViewSet)
router.register(r'affectations', AffectationConducteurViewSet)
router.register(r'reservations', ReservationVehiculeViewSet)
router.register(r'etats-des-lieux', EtatDesLieuxViewSet)
router.register(r'pleins', PleinCarburantViewSet)
router.register(r'cartes', CarteCarburantViewSet)
router.register(r'plans-entretien', PlanEntretienViewSet)
router.register(r'echeances-entretien', EcheanceEntretienViewSet)
router.register(r'garages', GarageViewSet)
router.register(r'garanties', GarantieFlotteViewSet)
router.register(r'ordres-reparation', OrdreReparationViewSet)
router.register(r'pneumatiques', PneumatiqueViewSet)
router.register(r'pieces', PieceFlotteViewSet)
router.register(r'echeances-reglementaires', EcheanceReglementaireViewSet)
router.register(r'baremes-vignette', BaremeVignetteViewSet)
router.register(r'assurances', AssuranceVehiculeViewSet)
router.register(r'visites-techniques', VisiteTechniqueViewSet)
router.register(r'cartes-grises', CarteGriseVehiculeViewSet)
router.register(r'sinistres', SinistreViewSet)
router.register(r'infractions', InfractionViewSet)
router.register(r'releves-telematiques', ReleveTelematiqueViewSet)
router.register(r'trajets-telematiques', TrajetTelematiqueViewSet)
router.register(r'trajets-chantier', TrajetChantierViewSet)
router.register(r'demandes-vehicule', DemandeVehiculeViewSet)
router.register(r'contrats-vehicule', ContratVehiculeViewSet)
router.register(r'couts', CoutVehiculeViewSet)
router.register(r'signalements', SignalementVehiculeViewSet)
router.register(r'modeles-inspection', ModeleInspectionViewSet)
router.register(r'inspections', InspectionVehiculeViewSet)
router.register(r'chartes-vehicule', CharteVehiculeViewSet)
router.register(r'accuses-charte', AccuseCharteViewSet)
router.register(r'budgets', BudgetFlotteViewSet)

urlpatterns = [
    path('rapports/couts/', rapport_couts, name='flotte-rapport-couts'),
    path('rapports/remplacement/', rapport_remplacement,
         name='flotte-rapport-remplacement'),
    path('rapports/budget/', rapport_budget, name='flotte-rapport-budget'),
    path('', include(router.urls)),
]
