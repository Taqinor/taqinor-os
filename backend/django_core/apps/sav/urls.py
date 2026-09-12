from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .views import (
    EquipementViewSet, TicketViewSet,
    SavSlaSettingsViewSet, MaintenanceChecklistTemplateViewSet,
    WarrantyClaimViewSet, KbArticleViewSet, AlarmeOnduleurViewSet,
    CauseDefaillanceViewSet, RemedeDefaillanceViewSet, ReponseTypeViewSet,
    CompatibilitePieceViewSet, CategorieTicketViewSet,
    EquipeMaintenanceViewSet, CategorieEquipementViewSet,
    WorksheetMaintenanceModeleViewSet, ProblemeViewSet,
    sav_parts_forecast, sav_pareto_pannes, sav_fiabilite_insight,
    sav_resume_par_equipe, sav_file_action, sav_file_attente,
)
from .public_views import portail_creer_ticket, whatsapp_inbound_webhook
from .maintenance import ContratMaintenanceViewSet

router = DefaultRouter()
router.register(r'equipements', EquipementViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'contrats-maintenance', ContratMaintenanceViewSet)
router.register(r'sla-settings', SavSlaSettingsViewSet)
router.register(r'checklist-templates', MaintenanceChecklistTemplateViewSet)
router.register(r'warranty-claims', WarrantyClaimViewSet)
router.register(r'kb-articles', KbArticleViewSet)
router.register(r'alarmes-onduleur', AlarmeOnduleurViewSet)
router.register(r'causes-defaillance', CauseDefaillanceViewSet)
router.register(r'remedes-defaillance', RemedeDefaillanceViewSet)
router.register(r'reponses-type', ReponseTypeViewSet)
router.register(r'compatibilites-piece', CompatibilitePieceViewSet)
router.register(r'categories-ticket', CategorieTicketViewSet)
router.register(r'equipes-maintenance', EquipeMaintenanceViewSet)
router.register(r'categories-equipement', CategorieEquipementViewSet)
router.register(r'worksheet-modeles', WorksheetMaintenanceModeleViewSet)
# NTSRV16 — Gestion Problème (problème ↔ incidents).
router.register(r'problemes', ProblemeViewSet)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def parts_forecast_view(request):
    """FG89 — Prévision de pièces SAV (interne, pas de prix achat)."""
    return sav_parts_forecast(request)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def pareto_pannes_view(request):
    """XSAV14 — Pareto des pannes par modèle de produit / fournisseur."""
    return sav_pareto_pannes(request)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def fiabilite_insight_view(request):
    """XSAV15 — MTBF/MTTR/coût cumulé, vue d'ensemble du parc."""
    return sav_fiabilite_insight(request)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def resume_par_equipe_view(request):
    """ZMFG4 — Tableau de bord SAV groupé par équipe. Responsable/admin."""
    return sav_resume_par_equipe(request)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def file_action_view(request):
    """ZSAV6 — File d'action suivante par ticket. Responsable/admin."""
    return sav_file_action(request)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def file_attente_view(request):
    """NTSRV8 — File d'attente par équipe + proposition de débordement.
    LECTURE PURE (aucune réaffectation). Responsable/admin."""
    return sav_file_attente(request)


urlpatterns = [
    # ZSAV6 — DOIT précéder `include(router.urls)` : sinon le routeur
    # capturerait `file-action` comme un `pk` de détail sur `tickets/<pk>/`.
    path('tickets/file-action/', file_action_view,
         name='sav-file-action'),
    # NTSRV2 — Formulaire portail client → ticket (PUBLIC, résolu par le jeton
    # du compte portail ; AllowAny + throttle déclarés sur la vue elle-même).
    path('portail/tickets/', portail_creer_ticket,
         name='sav-portail-creer-ticket'),
    # NTSRV3 — Webhook WhatsApp entrant (canal SAV). GATED : 404 tant que
    # WHATSAPP_BUSINESS_API_KEY n'est pas configurée.
    path('webhooks/whatsapp-inbound/', whatsapp_inbound_webhook,
         name='sav-whatsapp-inbound'),
    # NTSRV8 — File d'attente par équipe (+ proposition de débordement).
    path('file-attente/', file_attente_view, name='sav-file-attente'),
    path('', include(router.urls)),
    path('insights/sav-parts-forecast/', parts_forecast_view,
         name='sav-parts-forecast'),
    path('insights/sav-pannes/', pareto_pannes_view,
         name='sav-pareto-pannes'),
    path('insights/sav-fiabilite/', fiabilite_insight_view,
         name='sav-fiabilite'),
    path('insights/sav-resume-equipe/', resume_par_equipe_view,
         name='sav-resume-equipe'),
]
