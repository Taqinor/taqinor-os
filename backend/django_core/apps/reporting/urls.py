from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import dashboard
from .search import global_search, notifications
from .pipeline import pipeline, funnel_velocity
from .reports import (
    kpi_federes, sales_report, stock_report, service_report,
)
from .insights import (
    recurring_revenue, audit_log, job_costing, analytics, commissions,
    sales_leaderboard, cf_group_by, cohorts, profitability,
)
from .archive import archive_client, archive_chantier
from .calendar import (
    calendar_events, calendar_reschedule, calendar_ics,
    calendar_ics_subscription,
)
from .geo import geo_points
from .balance_export import balance_agee_export
from .saved_reports_api import SavedReportViewSet
from .commercial import commercial_dashboard, win_loss_by_source
from .dashboard_config_api import DashboardConfigViewSet
from .sav_sla import sav_sla_insight
from .approbations import (
    approbations_en_attente, decider_approbation, decider_en_masse,
)
from .kpi_alertes import KpiAlerteViewSet
from .classeur import ClasseurViewSet
from .integrity_views import integrite_insight
from .sav_pivot import sav_tickets_pivot, sav_tickets_cout_moyen, sav_taux_attache
from .reports_field import field_service_report
from .technicien_scorecard import technicien_scorecard
from .vitals import collect_vital, vitals_p75

# N79 — CRUD des rapports sauvegardés (router DRF, ajouté en additif).
# FG96 — CRUD + effective/ pour la config tableau de bord.
router = DefaultRouter()
router.register(r'saved-reports', SavedReportViewSet, basename='saved-report')
router.register(r'dashboard-config', DashboardConfigViewSet,
                basename='dashboard-config')
# XPLT6 — CRUD des alertes de seuil sur KPI agrégés.
router.register(r'kpi-alertes', KpiAlerteViewSet, basename='kpi-alerte')
# XPLT22 — classeur léger embarqué avec données live (mini-spreadsheet BI).
router.register(r'classeurs', ClasseurViewSet, basename='classeur')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', dashboard, name='reporting-dashboard'),
    path('search/', global_search, name='global-search'),
    path('notifications/', notifications, name='in-app-notifications'),
    path('calendar/', calendar_events, name='reporting-calendar'),
    path('calendar/reschedule/', calendar_reschedule,
         name='reporting-calendar-reschedule'),
    # FG6 — flux ICS/iCal par utilisateur (abonnement Google/Outlook). Le flux
    # est authentifié par jeton signé (?token=) — pas de session.
    path('calendar.ics', calendar_ics, name='reporting-calendar-ics'),
    path('calendar/subscription/', calendar_ics_subscription,
         name='reporting-calendar-ics-subscription'),
    path('geo/', geo_points, name='reporting-geo'),
    path('pipeline/', pipeline, name='reporting-pipeline'),
    path('pipeline/velocity/', funnel_velocity, name='reporting-funnel-velocity'),  # FG29
    path('reports/sales/', sales_report, name='report-sales'),
    path('reports/stock/', stock_report, name='report-stock'),
    path('reports/service/', service_report, name='report-service'),
    # ARC40 — KPI fédérés pilotés par le registre plateforme (kpi_providers).
    path('reports/kpi-federes/', kpi_federes, name='report-kpi-federes'),
    path('insights/recurring-revenue/', recurring_revenue,
         name='insights-recurring-revenue'),
    path('insights/audit-log/', audit_log, name='insights-audit-log'),
    path('insights/job-costing/', job_costing, name='insights-job-costing'),
    path('insights/analytics/', analytics, name='insights-analytics'),
    path('insights/commissions/', commissions, name='insights-commissions'),
    # FG93 — classement commerciaux (CA signé, taux victoire, deal moyen, kWc).
    path('insights/sales-leaderboard/', sales_leaderboard,
         name='insights-sales-leaderboard'),
    # FG94 — group-by sur un champ personnalisé visible_liste.
    # ?module=lead|client|produit|devis|installation|ticket &code=<code>.
    path('insights/cf-group-by/', cf_group_by, name='insights-cf-group-by'),
    # FG98 — cohortes leads par mois d'acquisition (taux signature + délai).
    path('insights/cohorts/', cohorts, name='insights-cohorts'),
    # FG99 — rentabilité par segment (ADMIN ; prix achat interne, jamais client-facing).
    path('insights/profitability/', profitability, name='insights-profitability'),
    path('archive/client/<int:pk>/', archive_client,
         name='reporting-archive-client'),
    path('archive/chantier/<int:pk>/', archive_chantier,
         name='reporting-archive-chantier'),
    # Export .xlsx de la balance âgée (créances par client + tranches d'âge),
    # borné à la société (miroir de l'export journal des ventes).
    path('balance-agee/export/', balance_agee_export,
         name='reporting-balance-agee-export'),
    # QJ18 — Tableau de bord commercial (entonnoir, vélocité, classement).
    path('commercial/dashboard/', commercial_dashboard,
         name='reporting-commercial-dashboard'),
    # QJ19 — Win/loss par canal/source + top motifs de perte.
    path('commercial/win-loss-by-source/', win_loss_by_source,
         name='reporting-win-loss-by-source'),
    # XSAV8 — conformité SLA + KPI SAV avancés (backlog vieilli, préventif vs
    # correctif, ponctualité des visites, réouvertures si disponibles).
    path('insights/sav-sla/', sav_sla_insight, name='insights-sav-sla'),
    # XKB1 — boîte d'approbations centralisée cross-app.
    path('approbations-en-attente/', approbations_en_attente,
         name='reporting-approbations-en-attente'),
    path('approbations-en-attente/decider/', decider_approbation,
         name='reporting-approbations-decider'),
    path('approbations-en-attente/decider-en-masse/', decider_en_masse,
         name='reporting-approbations-decider-masse'),
    # YSERV13 — contrôle d'intégrité inter-documents (états orphelins).
    path('insights/integrite/', integrite_insight, name='insights-integrite'),
    # ZSAV7 — pivot tickets SAV (dataset core.data_explorer sav_tickets).
    path('insights/sav-tickets-pivot/', sav_tickets_pivot,
         name='insights-sav-tickets-pivot'),
    path('insights/sav-tickets-cout-moyen/', sav_tickets_cout_moyen,
         name='insights-sav-tickets-cout-moyen'),
    # YSERV10 — KPI taux d'attache (chantiers réceptionnés avec contrat
    # d'entretien actif ≤90j).
    path('insights/sav-taux-attache/', sav_taux_attache,
         name='insights-sav-taux-attache'),
    # XFSM16 — analytics field service consolidés (FTF, MTTR, ponctualité,
    # récidive, trajet vs sur site, interventions par type/statut).
    path('reports/field/', field_service_report, name='report-field-service'),
    # XFSM17 — scorecard coaching par technicien vs moyenne équipe.
    path('insights/technicien-scorecard/', technicien_scorecard,
         name='insights-technicien-scorecard'),
    # VX61 — beacon Web Vitals RÉELS (POST, une ligne/métrique) + agrégat p75.
    path('vitals/', collect_vital, name='reporting-vitals'),
    path('vitals/p75/', vitals_p75, name='reporting-vitals-p75'),
]
