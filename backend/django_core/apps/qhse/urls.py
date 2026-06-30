from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionCorrectivePreventiveViewSet, AnalyseIncidentViewSet, AuditViewSet,
    CauseIncidentViewSet, ConsignationLotoViewSet,
    ContactUrgenceViewSet,
    CritereAuditViewSet, DeclarationCnssViewSet,
    EvaluationRisqueViewSet, GrilleAuditViewSet, IncidentViewSet,
    InductionSecuriteViewSet,
    Iso9001ReadinessViewSet,
    ItemNotationViewSet, LigneEvaluationRisqueViewSet,
    NonConformiteViewSet, NotationFinChantierViewSet, PermisTravailViewSet,
    PlanInspectionChantierViewSet, PlanInspectionModeleViewSet,
    PlanUrgenceViewSet,
    PointControleModeleViewSet, ProcedureQualiteViewSet,
    QhseChatterEntryViewSet,
    ReleveControleViewSet, ReleveCourbeIVViewSet, ReponseCritereViewSet,
    RetourClientQualiteViewSet, SecouristeViewSet,
)

router = DefaultRouter()
router.register(r'non-conformites', NonConformiteViewSet)
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
router.register(r'analyses-incident', AnalyseIncidentViewSet)
router.register(r'causes-incident', CauseIncidentViewSet)
router.register(
    r'iso9001-readiness', Iso9001ReadinessViewSet,
    basename='iso9001-readiness')

urlpatterns = [
    path('', include(router.urls)),
]
