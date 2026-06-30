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
from rest_framework.routers import DefaultRouter

from .views import (
    BrandedTemplateViewSet,
    BulkEditViewSet,
    DashboardViewSet,
    ModuleToggleViewSet,
    PaymentTransactionViewSet,
    SavedQueryViewSet,
    ScheduledExportViewSet,
    ScheduledJobViewSet,
    TenantThemeViewSet,
    TrashViewSet,
    WorkflowTemplateViewSet,
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
# FG392 — thème white-label par société (singleton, lecture/upsert).
router.register(r'theme', TenantThemeViewSet, basename='tenant-theme')
# FG393 — éditeur de modèles imprimables/brandés (PDF/email/WhatsApp).
router.register(r'branded-templates', BrandedTemplateViewSet,
                basename='branded-template')

urlpatterns = router.urls
