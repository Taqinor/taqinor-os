"""URLs de la couche fondation ``core``.

FG368 — endpoint des jobs planifiés (Celery Beat).

  GET  jobs/      → liste des jobs configurés
  POST jobs/run/  → exécution manuelle (admin uniquement)

WIRING : ``core`` n'avait pas d'URLConf jusqu'ici. Pour exposer ces routes,
ajouter UNE ligne au routeur racine ``erp_agentique/urls.py`` (hors de ce
fichier, donc non modifié par cette tâche « core-only ») :

    path('api/django/core/', include('core.urls')),
"""
from rest_framework.routers import DefaultRouter

from .views import ScheduledJobViewSet

router = DefaultRouter()
router.register(r'jobs', ScheduledJobViewSet, basename='scheduled-job')

urlpatterns = router.urls
