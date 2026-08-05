from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, views_licences

router = DefaultRouter()
router.register(r'sandbox', views.SandboxEnvironmentViewSet, basename='sandboxenvironment')
router.register(r'config-packages', views.ConfigPackageViewSet, basename='configpackage')

urlpatterns = [
    path('health-score/', views.health_score_view, name='adminops-health-score'),
    path('adoption/', views.adoption_view, name='adminops-adoption'),
    path('tracker-usage/', views.tracker_usage_view, name='adminops-tracker-usage'),
    path('settings/', views.AdminOpsSettingsView.as_view(), name='adminops-settings'),
    path('diagnostic/', views.diagnostic_view, name='adminops-diagnostic'),
    path('diagnostic/support-bundle/', views.support_bundle_view,
         name='adminops-support-bundle'),
    path('rapports/journal-admin/', views.journal_admin_pdf_view,
         name='adminops-journal-admin'),
    # NTADM8/9 — statut de licence (plan, modules, sièges, historique).
    path('licences/', views_licences.licence_statut_view,
         name='adminops-licence-statut'),
    path('', include(router.urls)),
]
