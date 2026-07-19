from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionCorrectivePreventiveViewSet, AnalyseIncidentViewSet,
    AspectEnvironnementalViewSet, AuditViewSet,
    BilanCarboneViewSet, BordereauSuiviDechetViewSet,
    CalendrierQhseViewSet,
    causerie_securite_pdf,
    CauseIncidentViewSet, ConformiteEnvironnementaleViewSet,
    ConsignationLotoViewSet,
    CodeDefautViewSet,
    ContactUrgenceViewSet, ControleReceptionViewSet, DechetViewSet,
    CritereAuditViewSet, DeclarationCnssViewSet, DemandeChangementViewSet,
    DerogationViewSet,
    EtapeDeclarationAtViewSet,
    CoutNonQualiteViewSet,
    EvaluationRisqueViewSet, ExerciceUrgenceViewSet, GrilleAuditViewSet,
    IncidentViewSet,
    IndicateurESGViewSet,
    ia_suggestion_analyse, ia_suggestion_classification,
    InductionSecuriteViewSet, InspectionSecuriteViewSet,
    Iso9001ReadinessViewSet,
    ItemNotationViewSet, LienSignalementPublicViewSet,
    LigneEvaluationRisqueViewSet,
    NonConformiteViewSet, NotationFinChantierViewSet,
    ObservationSecuriteViewSet,
    ParetoDefautsViewSet, PermisTravailViewSet,
    PlanControleReceptionViewSet, PlanInspectionChantierViewSet,
    PlanInspectionModeleViewSet,
    PlanUrgenceViewSet,
    LigneBilanCarboneViewSet,
    PointControleModeleViewSet, PointControleReceptionViewSet,
    ProcedureQualiteViewSet, public_signalement,
    QhseChatterEntryViewSet, RecyclageModuleViewSet,
    ReleveConsommationViewSet, ReleveControleViewSet, ReleveCourbeIVViewSet,
    ReponseCritereViewSet,
    RetourClientQualiteViewSet, RevueVeilleReglementaireViewSet,
    SecouristeViewSet, SignalementPublicViewSet,
    VeilleReglementaireViewSet,
    CheckinSecuriteViewSet, DemandeActionFournisseurViewSet,
)

router = DefaultRouter()
router.register(r'non-conformites', NonConformiteViewSet)
router.register(r'derogations', DerogationViewSet)
router.register(r'capa', ActionCorrectivePreventiveViewSet)
router.register(r'plans-inspection', PlanInspectionModeleViewSet)
router.register(r'points-controle', PointControleModeleViewSet)
router.register(r'plans-chantier', PlanInspectionChantierViewSet)
router.register(r'releves', ReleveControleViewSet)
router.register(r'courbes-iv', ReleveCourbeIVViewSet)
router.register(r'chatter', QhseChatterEntryViewSet)
router.register(r'grilles-audit', GrilleAuditViewSet)
router.register(r'criteres-audit', CritereAuditViewSet)
router.register(r'audits', AuditViewSet)
router.register(r'reponses-critere', ReponseCritereViewSet)
router.register(r'notations-fin-chantier', NotationFinChantierViewSet)
router.register(r'items-notation', ItemNotationViewSet)
router.register(r'procedures-qualite', ProcedureQualiteViewSet)
router.register(r'retours-client', RetourClientQualiteViewSet)
router.register(r'evaluations-risque', EvaluationRisqueViewSet)
router.register(r'lignes-evaluation-risque', LigneEvaluationRisqueViewSet)
router.register(r'permis-travail', PermisTravailViewSet)
router.register(r'consignations-loto', ConsignationLotoViewSet)
router.register(r'inductions-securite', InductionSecuriteViewSet)
router.register(r'plans-urgence', PlanUrgenceViewSet)
router.register(r'contacts-urgence', ContactUrgenceViewSet)
router.register(r'secouristes', SecouristeViewSet)
router.register(r'incidents', IncidentViewSet)
router.register(r'declarations-cnss', DeclarationCnssViewSet)
router.register(r'etapes-declaration-at', EtapeDeclarationAtViewSet)
router.register(r'analyses-incident', AnalyseIncidentViewSet)
router.register(r'causes-incident', CauseIncidentViewSet)
router.register(r'inspections-securite', InspectionSecuriteViewSet)
router.register(r'dechets', DechetViewSet)
router.register(r'bordereaux-dechets', BordereauSuiviDechetViewSet)
router.register(r'recyclage-modules', RecyclageModuleViewSet)
router.register(
    r'conformites-environnementales', ConformiteEnvironnementaleViewSet)
router.register(r'bilans-carbone', BilanCarboneViewSet)
router.register(r'lignes-bilan-carbone', LigneBilanCarboneViewSet)
router.register(r'indicateurs-esg', IndicateurESGViewSet)
router.register(
    r'iso9001-readiness', Iso9001ReadinessViewSet,
    basename='iso9001-readiness')
router.register(
    r'calendrier', CalendrierQhseViewSet, basename='calendrier')
router.register(
    r'plans-controle-reception', PlanControleReceptionViewSet)
router.register(
    r'points-controle-reception', PointControleReceptionViewSet)
router.register(r'controles-reception', ControleReceptionViewSet)
router.register(r'codes-defaut', CodeDefautViewSet)
router.register(
    r'pareto-defauts', ParetoDefautsViewSet, basename='pareto-defauts')
router.register(
    r'liens-signalement', LienSignalementPublicViewSet)
router.register(r'signalements-publics', SignalementPublicViewSet)
router.register(r'observations-securite', ObservationSecuriteViewSet)
router.register(r'exercices-urgence', ExerciceUrgenceViewSet)
router.register(r'aspects-environnementaux', AspectEnvironnementalViewSet)
router.register(r'releves-consommation', ReleveConsommationViewSet)
router.register(
    r'cout-non-qualite', CoutNonQualiteViewSet, basename='cout-non-qualite')
router.register(r'demandes-changement', DemandeChangementViewSet)
router.register(r'veilles-reglementaires', VeilleReglementaireViewSet)
router.register(r'revues-veille', RevueVeilleReglementaireViewSet)
# WIR115 — Check-in sécurité (technicien seul sur site) + SCAR (demande
# d'action corrective fournisseur), jusqu'ici sans exposition REST.
router.register(r'checkins-securite', CheckinSecuriteViewSet)
router.register(r'demandes-action-fournisseur', DemandeActionFournisseurViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # XQHS16 — endpoint PUBLIC tokenisé (sans login), en dehors du router
    # authentifié. Le préfixe `public/` ne doit jamais être capté par une
    # route authentifiée (même motif que ged.urls `public/<token>/`).
    path('public/signalement/<str:token>/', public_signalement,
         name='qhse-public-signalement'),
    # XQHS25 — assistance IA QHSE (key-gated, authentifié — pas public).
    path('ia/suggestion-classification/', ia_suggestion_classification,
         name='qhse-ia-suggestion-classification'),
    path('ia/suggestion-analyse/', ia_suggestion_analyse,
         name='qhse-ia-suggestion-analyse'),
    # XQHS27 — causerie sécurité (rh.CauserieSecurite) : PDF imprimable
    # bilingue FR/AR, lu via apps.rh.selectors (jamais rh.models/rh.views).
    path('causeries/<int:causerie_id>/pdf/', causerie_securite_pdf,
         name='qhse-causerie-securite-pdf'),
]
