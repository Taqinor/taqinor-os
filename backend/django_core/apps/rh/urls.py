from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import public_views
from .views import (
    AccidentTravailViewSet,
    AffectationRosterViewSet,
    AffectationVehiculeViewSet,
    AnalyseRisquesChantierViewSet,
    AttributionBadgeViewSet,
    AvanceSalaireViewSet,
    AvantageSocialViewSet,
    AyantDroitViewSet,
    BadgeReconnaissanceViewSet,
    BesoinFormationViewSet,
    BulletinPaieViewSet,
    CampagneEvaluationViewSet,
    CampagnePulseViewSet,
    CandidatureViewSet,
    CauserieSecuriteViewSet,
    CockpitRhViewSet,
    CertificationViewSet,
    CompetenceEmployeViewSet,
    CompetenceRequiseViewSet,
    CompetenceViewSet,
    DemandeAllocationViewSet,
    DemandeCongeViewSet,
    DemandeRHViewSet,
    DepartementViewSet,
    DeviceKiosqueViewSet,
    DocumentEmployeViewSet,
    DossierEmployeViewSet,
    DotationEpiViewSet,
    EcheancesRhViewSet,
    EmployeDeviceMapViewSet,
    ElementIntegrationEmployeViewSet,
    ElementIntegrationViewSet,
    ElementSortieViewSet,
    ElementsVariablesPaieViewSet,
    EntretienRecrutementViewSet,
    EntretienSortieViewSet,
    EpiCatalogueViewSet,
    GabaritEmailRecrutementViewSet,
    GrilleSalarialeViewSet,
    EvaluationEmployeViewSet,
    FeuilleTempsViewSet,
    HabilitationViewSet,
    HeuresSuppViewSet,
    HoraireTravailViewSet,
    IncidentPresenceViewSet,
    JourBloqueCongeViewSet,
    KiosquePointageViewSet,
    ModeleEvaluationViewSet,
    ModeleIntegrationViewSet,
    NoteDeFraisViewSet,
    OrdreMissionViewSet,
    OuverturePosteViewSet,
    PeriodeFermetureViewSet,
    PermisConduireViewSet,
    PointageViewSet,
    PortailSelfServiceViewSet,
    PosteViewSet,
    PresenceChantierViewSet,
    PresquAccidentViewSet,
    PrimeAttribueeViewSet,
    PromesseEmbaucheViewSet,
    QuizFormationViewSet,
    RecrutementStatistiquesViewSet,
    ReglageRHViewSet,
    RemunerationViewSet,
    SanctionViewSet,
    SessionFormationViewSet,
    SoldeCongeViewSet,
    TableauBordHseViewSet,
    TentativeQuizViewSet,
    TypeAbsenceViewSet,
    TypePrimeViewSet,
    VisiteMedicaleViewSet,
)

router = DefaultRouter()
router.register(r'departements', DepartementViewSet)
router.register(r'postes', PosteViewSet)
router.register(r'horaires-travail', HoraireTravailViewSet)
router.register(r'employes', DossierEmployeViewSet)
router.register(r'remunerations', RemunerationViewSet)
router.register(r'grilles-salariales', GrilleSalarialeViewSet)
router.register(r'documents', DocumentEmployeViewSet)
router.register(r'elements-sortie', ElementSortieViewSet)
router.register(r'entretiens-sortie', EntretienSortieViewSet)
router.register(r'ayants-droit', AyantDroitViewSet)
router.register(r'avantages-sociaux', AvantageSocialViewSet)
router.register(r'modeles-integration', ModeleIntegrationViewSet)
router.register(r'elements-integration', ElementIntegrationViewSet)
router.register(
    r'elements-integration-employe', ElementIntegrationEmployeViewSet)
router.register(r'types-absence', TypeAbsenceViewSet)
router.register(r'soldes-conge', SoldeCongeViewSet)
router.register(r'demandes-conge', DemandeCongeViewSet)
router.register(r'demandes-allocation', DemandeAllocationViewSet)
router.register(r'jours-bloques-conge', JourBloqueCongeViewSet)
router.register(r'periodes-fermeture', PeriodeFermetureViewSet)
# NOTE : le kiosque (``pointages/kiosque``) DOIT être enregistré AVANT
# ``pointages`` — DefaultRouter résout dans l'ordre d'enregistrement, et le
# pattern détail de ``pointages`` (``pointages/<pk>/``) matcherait sinon
# ``pointages/kiosque/`` en traitant "kiosque" comme un pk, ce qui route vers
# PointageViewSet (authentifié) au lieu du guichet kiosque (AllowAny) → 401
# au lieu du comportement attendu.
router.register(
    r'pointages/kiosque', KiosquePointageViewSet, basename='rh-kiosque')
router.register(r'pointages', PointageViewSet)
router.register(r'devices-kiosque', DeviceKiosqueViewSet)
router.register(r'devices-employe-map', EmployeDeviceMapViewSet)
router.register(r'reglages', ReglageRHViewSet, basename='rh-reglages')
router.register(r'feuilles-temps', FeuilleTempsViewSet)
router.register(r'heures-supp', HeuresSuppViewSet)
router.register(r'roster', AffectationRosterViewSet)
router.register(r'presences-chantier', PresenceChantierViewSet)
router.register(r'incidents-presence', IncidentPresenceViewSet)
router.register(r'competences', CompetenceViewSet)
router.register(r'competences-employe', CompetenceEmployeViewSet)
router.register(r'competences-requises', CompetenceRequiseViewSet)
router.register(r'habilitations', HabilitationViewSet)
router.register(r'certifications', CertificationViewSet)
router.register(r'visites-medicales', VisiteMedicaleViewSet)
router.register(r'epi-catalogue', EpiCatalogueViewSet)
router.register(r'dotations-epi', DotationEpiViewSet)
router.register(r'echeances', EcheancesRhViewSet, basename='rh-echeances')
router.register(
    r'tableau-bord-hse', TableauBordHseViewSet, basename='rh-tableau-bord-hse')
router.register(r'accidents-travail', AccidentTravailViewSet)
router.register(r'presqu-accidents', PresquAccidentViewSet)
router.register(r'causeries-securite', CauserieSecuriteViewSet)
router.register(r'analyses-risques-chantier', AnalyseRisquesChantierViewSet)
router.register(r'sessions-formation', SessionFormationViewSet)
router.register(r'besoins-formation', BesoinFormationViewSet)
router.register(r'quiz-formation', QuizFormationViewSet)
router.register(r'tentatives-quiz', TentativeQuizViewSet)
router.register(r'ouvertures-poste', OuverturePosteViewSet)
router.register(r'candidatures', CandidatureViewSet)
router.register(
    r'recrutement/statistiques', RecrutementStatistiquesViewSet,
    basename='rh-recrutement-statistiques')
router.register(r'entretiens-recrutement', EntretienRecrutementViewSet)
router.register(r'gabarits-email-recrutement', GabaritEmailRecrutementViewSet)
router.register(r'promesses-embauche', PromesseEmbaucheViewSet)
router.register(r'modeles-evaluation', ModeleEvaluationViewSet)
router.register(r'campagnes-evaluation', CampagneEvaluationViewSet)
router.register(r'campagnes-pulse', CampagnePulseViewSet)
router.register(r'evaluations-employe', EvaluationEmployeViewSet)
router.register(r'sanctions', SanctionViewSet)
router.register(r'elements-variables-paie', ElementsVariablesPaieViewSet)
router.register(r'types-prime', TypePrimeViewSet)
router.register(r'primes-attribuees', PrimeAttribueeViewSet)
router.register(r'ordres-mission', OrdreMissionViewSet)
router.register(r'avances-salaire', AvanceSalaireViewSet)
router.register(r'bulletins-paie', BulletinPaieViewSet)
router.register(r'permis-conduire', PermisConduireViewSet)
router.register(r'affectations-vehicule', AffectationVehiculeViewSet)
router.register(r'notes-frais', NoteDeFraisViewSet)
router.register(r'demandes-rh', DemandeRHViewSet)
router.register(
    r'portail', PortailSelfServiceViewSet, basename='rh-portail')
router.register(r'cockpit', CockpitRhViewSet, basename='rh-cockpit')
router.register(r'badges-reconnaissance', BadgeReconnaissanceViewSet)
router.register(r'attributions-badge', AttributionBadgeViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # XRH20 — liens publics tokenisés de la promesse d'embauche (sans session).
    path('promesses-embauche/public/<str:token>/',
         public_views.public_promesse_detail,
         name='rh-promesse-publique-detail'),
    path('promesses-embauche/public/<str:token>/pdf/',
         public_views.public_promesse_pdf,
         name='rh-promesse-publique-pdf'),
    path('promesses-embauche/public/<str:token>/signer/',
         public_views.public_promesse_signer,
         name='rh-promesse-publique-signer'),
    # XRH33 — page carrières publique (flag-gated OFF par défaut, 404 sinon).
    path('carrieres/<slug:company_slug>/',
         public_views.careers_list,
         name='rh-carrieres-liste'),
    path('carrieres/<slug:company_slug>/<int:ouverture_id>/candidater/',
         public_views.careers_apply,
         name='rh-carrieres-candidater'),
]
