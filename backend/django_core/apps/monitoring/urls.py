from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AbonnementMonitoringViewSet, CleaningEventViewSet,
    MonitoringConfigViewSet, MonitoringSettingsViewSet,
    ProductionReadingViewSet, ProductionWarrantyViewSet,
)

router = DefaultRouter()
router.register(r'configs', MonitoringConfigViewSet)
router.register(r'readings', ProductionReadingViewSet)
router.register(r'warranties', ProductionWarrantyViewSet)
router.register(r'cleanings', CleaningEventViewSet)
router.register(r'settings', MonitoringSettingsViewSet)
# ASAV100 — abonnements de supervision (D-ASAV-4 option (b)).
router.register(r'abonnements', AbonnementMonitoringViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
