"""URLs de la couche fondation ``core``.

FG368 — endpoint des jobs planifiés (Celery Beat).

  GET  jobs/      → liste des jobs configurés
  POST jobs/run/  → exécution manuelle (admin uniquement)

FG369 — bibliothèque de modèles de workflow installables.

  GET  workflow-templates/            → catalogue des modèles disponibles
  POST workflow-templates/installer/  → installe un modèle (admin/responsable)

WIRING : ``core`` n'avait pas d'URLConf jusqu'ici. Pour exposer ces routes,
ajouter UNE ligne au routeur racine ``erp_agentique/urls.py`` (hors de ce
fichier, donc non modifié par cette tâche « core-only ») :

    path('api/django/core/', include('core.urls')),
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .dashboard_partage import (
    DashboardPartageInterneViewSet,
    PartageDashboardViewSet,
    dashboard_public,
    dashboard_tv,
)
from .views import (
    ApiUsagePlanViewSet,
    BackgroundJobViewSet,
    BackupRunViewSet,
    BrandedTemplateViewSet,
    BulkEditViewSet,
    ChangelogViewSet,
    ConsentRecordViewSet,
    DashboardViewSet,
    DataSubjectRequestViewSet,
    ModuleCatalogViewSet,
    ModuleToggleViewSet,
    OutboxEventViewSet,
    PaymentTransactionViewSet,
    RegistreTraitementViewSet,
    SavedQueryViewSet,
    ScheduledExportViewSet,
    ScheduledJobViewSet,
    SystemStatusViewSet,
    TenantThemeViewSet,
    TenantUsageSnapshotViewSet,
    TrashViewSet,
    WorkflowTemplateViewSet,
    health_live,
    health_ready,
    maintenance_toggle,
    metrics_view,
    secrets_rotation_due,
)

router = DefaultRouter()
router.register(r'jobs', ScheduledJobViewSet, basename='scheduled-job')
router.register(r'workflow-templates', WorkflowTemplateViewSet,
                basename='workflow-template')
# FG381 — dashboards sans-code (CRUD multi-tenant, scoping perso/partagé).
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
# FG370 — paiement carte en ligne d'une facture (CMI / Payzone, gated).
router.register(r'paiements-en-ligne', PaymentTransactionViewSet,
                basename='payment-transaction')
# FG382 — explorateur de données : requêtes ad-hoc sauvegardées + run.
router.register(r'saved-queries', SavedQueryViewSet, basename='saved-query')
# FG383 — extraits planifiés vers SFTP/S3 (gated).
router.register(r'scheduled-exports', ScheduledExportViewSet,
                basename='scheduled-export')
# FG388 — corbeille par société + restauration + fenêtre d'undo.
router.register(r'corbeille', TrashViewSet, basename='trash')
# FG389 — édition de champ en masse, généralisée (cibles enregistrées).
router.register(r'bulk-edit', BulkEditViewSet, basename='bulk-edit')
# FG391 — flags de modules par société (activation/désactivation).
router.register(r'module-toggles', ModuleToggleViewSet,
                basename='module-toggle')
# ODX3 — catalogue de modules (manifests + état) + activer/désactiver avec
# fermeture de dépendances.
router.register(r'modules', ModuleCatalogViewSet, basename='module-catalog')
# FG392 — thème white-label par société (singleton, lecture/upsert).
router.register(r'theme', TenantThemeViewSet, basename='tenant-theme')
# FG393 — éditeur de modèles imprimables/brandés (PDF/email/WhatsApp).
router.register(r'branded-templates', BrandedTemplateViewSet,
                basename='branded-template')
# FG394 — consentement & DSR (loi 09-08 / CNDP).
router.register(r'consent-records', ConsentRecordViewSet,
                basename='consent-record')
router.register(r'dsr-requests', DataSubjectRequestViewSet,
                basename='dsr-request')
# XPLT23 — registre des traitements CNDP (loi 09-08).
router.register(r'registre-traitements', RegistreTraitementViewSet,
                basename='registre-traitement')
# FG395 — sauvegarde/restauration en libre-service (par société).
router.register(r'sauvegardes', BackupRunViewSet, basename='backup-run')
# FG397 — page d'état / santé système (services + incidents récents).
router.register(r'status', SystemStatusViewSet, basename='system-status')
# FG398 — plan de tarif API & analytics d'usage (singleton + analytics).
router.register(r'api-usage', ApiUsagePlanViewSet, basename='api-usage')
# FG399 — journal des nouveautés in-app (changelog) + suivi de lecture.
router.register(r'changelog', ChangelogViewSet, basename='changelog')
# NTPLT6 — compteurs d'usage par tenant (metering), SUPERUSER only.
router.register(r'usage', TenantUsageSnapshotViewSet, basename='tenant-usage')
# NTPLT29 — mes jobs de fond avec progression (scopé user + société).
router.register(r'jobs-status', BackgroundJobViewSet, basename='background-job')
# NTPLT10 — supervision de l'outbox transactionnel (SUPERUSER only).
router.register(r'outbox', OutboxEventViewSet, basename='outbox-event')
# XPLT10 — liens publics tokenisés + partage interne fin de dashboards.
router.register(r'dashboards-partages', PartageDashboardViewSet,
                basename='dashboard-partage')
router.register(r'dashboards-partages-internes',
                DashboardPartageInterneViewSet,
                basename='dashboard-partage-interne')

urlpatterns = router.urls + [
    # XPLT10 — accès public lecture seule (aucune identité de confiance,
    # résolu depuis le seul jeton) + mode TV (rotation des dashboards partagés).
    path('dashboards-partages/public/<str:token>/', dashboard_public,
         name='dashboard-partage-public'),
    path('dashboards-tv/', dashboard_tv, name='dashboard-tv'),
    # YOPSB14 — probes readiness/liveness légers, non authentifiés, jamais
    # de données société (à sonder par nginx/Caddy avant de router).
    path('health/live/', health_live, name='health-live'),
    path('health/ready/', health_ready, name='health-ready'),
    # YHARD5 — tableau « Secrets & rotation » (admin-only, jamais la valeur).
    path('secrets/rotation/', secrets_rotation_due, name='secrets-rotation-due'),
    # YHARD6 — métriques Prometheus (admin OU IP-allowlist, jamais public).
    path('metrics/', metrics_view, name='metrics'),
    # NTPLT55 — bascule superuser du mode maintenance (lecture seule).
    path('maintenance/', maintenance_toggle, name='maintenance-toggle'),
]
