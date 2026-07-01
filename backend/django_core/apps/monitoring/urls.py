from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CleaningEventViewSet, MonitoringConfigViewSet, MonitoringSettingsViewSet,
    ProductionReadingViewSet, ProductionWarrantyViewSet,
)

router = DefaultRouter()
router.register(r'configs', MonitoringConfigViewSet)
router.register(r'readings', ProductionReadingViewSet)
router.register(r'warranties', ProductionWarrantyViewSet)
router.register(r'cleanings', CleaningEventViewSet)
router.register(r'settings', MonitoringSettingsViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
