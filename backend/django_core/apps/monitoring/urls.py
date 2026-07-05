from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AbonnementMonitoringViewSet, CleaningEventViewSet, MonitoringConfigViewSet,
    MonitoringSettingsViewSet, ProductionReadingViewSet,
    ProductionWarrantyViewSet,
)

router = DefaultRouter()
router.register(r'configs', MonitoringConfigViewSet)
router.register(r'readings', ProductionReadingViewSet)
router.register(r'warranties', ProductionWarrantyViewSet)
router.register(r'cleanings', CleaningEventViewSet)
router.register(r'settings', MonitoringSettingsViewSet)
# ODX16 — nouvelle route ``/api/django/monitoring/abonnements-monitoring/`` ; la
# même classe est AUSSI servie sous ``/api/django/compta/abonnements-monitoring/``
# (route historique conservée). Basename préfixé ``mon-`` pour ne pas entrer en
# collision avec le routeur compta.
router.register(r'abonnements-monitoring', AbonnementMonitoringViewSet,
                basename='mon-abonnement-monitoring')

urlpatterns = [
    path('', include(router.urls)),
]
