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
    DashboardViewSet,
    ScheduledJobViewSet,
    WorkflowTemplateViewSet,
)

router = DefaultRouter()
router.register(r'jobs', ScheduledJobViewSet, basename='scheduled-job')
router.register(r'workflow-templates', WorkflowTemplateViewSet,
                basename='workflow-template')
# FG381 — dashboards sans-code (CRUD multi-tenant, scoping perso/partagé).
router.register(r'dashboards', DashboardViewSet, basename='dashboard')

urlpatterns = router.urls
