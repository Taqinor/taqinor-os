from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionCorrectivePreventiveViewSet, AnalyseIncidentViewSet, AuditViewSet,
    BilanCarboneViewSet, BordereauSuiviDechetViewSet,
    CalendrierQhseViewSet,
    CauseIncidentViewSet, ConformiteEnvironnementaleViewSet,
    ConsignationLotoViewSet,
    ContactUrgenceViewSet, ControleReceptionViewSet, DechetViewSet,
    CritereAuditViewSet, DeclarationCnssViewSet, DerogationViewSet,
    EtapeDeclarationAtViewSet,
    EvaluationRisqueViewSet, GrilleAuditViewSet, IncidentViewSet,
    IndicateurESGViewSet,
    InductionSecuriteViewSet, InspectionSecuriteViewSet,
    Iso9001ReadinessViewSet,
    ItemNotationViewSet, LigneEvaluationRisqueViewSet,
    NonConformiteViewSet, NotationFinChantierViewSet, PermisTravailViewSet,
    PlanControleReceptionViewSet, PlanInspectionChantierViewSet,
    PlanInspectionModeleViewSet,
    PlanUrgenceViewSet,
    LigneBilanCarboneViewSet,
    PointControleModeleViewSet, PointControleReceptionViewSet,
    ProcedureQualiteViewSet,
    QhseChatterEntryViewSet, RecyclageModuleViewSet,
    ReleveControleViewSet, ReleveCourbeIVViewSet, ReponseCritereViewSet,
    RetourClientQualiteViewSet, SecouristeViewSet,
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

urlpatterns = [
    path('', include(router.urls)),
]
