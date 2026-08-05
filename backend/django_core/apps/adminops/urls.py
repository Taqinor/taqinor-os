from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, views_impersonation

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
    # NTADM22/NTADM32 — sessions d'impersonation sous consentement.
    path('impersonation/',
         views_impersonation.ImpersonationDemandeView.as_view(),
         name='adminops-impersonation-demande'),
    path('impersonation/en-attente/',
         views_impersonation.ImpersonationEnAttenteView.as_view(),
         name='adminops-impersonation-en-attente'),
    path('impersonation/session-active/',
         views_impersonation.ImpersonationSessionActiveView.as_view(),
         name='adminops-impersonation-session-active'),
    path('impersonation/<int:pk>/consentir/',
         views_impersonation.ImpersonationConsentirView.as_view(),
         name='adminops-impersonation-consentir'),
    path('impersonation/<int:pk>/refuser/',
         views_impersonation.ImpersonationRefuserView.as_view(),
         name='adminops-impersonation-refuser'),
    path('impersonation/<int:pk>/demarrer/',
         views_impersonation.ImpersonationDemarrerView.as_view(),
         name='adminops-impersonation-demarrer'),
    path('impersonation/<int:pk>/terminer/',
         views_impersonation.ImpersonationTerminerView.as_view(),
         name='adminops-impersonation-terminer'),
    path('', include(router.urls)),
]
