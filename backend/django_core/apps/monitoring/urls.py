from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    MonitoringConfigViewSet, MonitoringSettingsViewSet,
    ProductionReadingViewSet,
)

router = DefaultRouter()
router.register(r'configs', MonitoringConfigViewSet)
router.register(r'readings', ProductionReadingViewSet)
router.register(r'settings', MonitoringSettingsViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
