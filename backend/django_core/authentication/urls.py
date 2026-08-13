from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    RegisterCompanyView,
    UserViewSet,
    CompanyViewSet,
    MeView,
    MobileHomeRouteView,
    LogoutView,
    CookieTokenRefreshView,
    TwoFactorSetupView,
    TwoFactorEnableView,
    TwoFactorDisableView,
    TwoFactorStatusView,
    SessionListView,
    SessionRevokeView,
    ChangePasswordView,
    SwitchCompanyView,
)
from .views_console_create import TenantConsoleCreateView
from .views_console import (
    TenantConsoleListView,
    TenantConsoleStatutView,
    TenantConsoleNoteView,
)
from .views_demo_wizard import DemoWizardCreateView, DemoWizardStatusView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'companies', CompanyViewSet, basename='companies')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path(
        'auth/register-company/',
        RegisterCompanyView.as_view(),
        name='auth_register_company',
    ),
    path('auth/me/', MeView.as_view(), name='auth_me'),
    # NTMOB6 — sélecteur de démarrage par rôle : réglage d'accueil mobile
    # mémorisé par l'utilisateur courant.
    path('auth/mobile-home-route/', MobileHomeRouteView.as_view(),
         name='auth_mobile_home_route'),
    # XPLT19 — bascule de société active (utilisateur multi-sociétés).
    path('auth/switch-company/', SwitchCompanyView.as_view(),
         name='auth_switch_company'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('auth/token/refresh/', CookieTokenRefreshView.as_view(), name='auth_token_refresh'),
    # Double authentification (2FA TOTP) — opt-in par utilisateur (N96).
    path('auth/2fa/status/', TwoFactorStatusView.as_view(), name='auth_2fa_status'),
    path('auth/2fa/setup/', TwoFactorSetupView.as_view(), name='auth_2fa_setup'),
    path('auth/2fa/enable/', TwoFactorEnableView.as_view(), name='auth_2fa_enable'),
    path('auth/2fa/disable/', TwoFactorDisableView.as_view(), name='auth_2fa_disable'),
    # Sessions actives & révocation + rotation du mot de passe (N96).
    path('auth/sessions/', SessionListView.as_view(), name='auth_sessions'),
    path('auth/sessions/<int:pk>/revoke/', SessionRevokeView.as_view(),
         name='auth_session_revoke'),
    path('auth/change-password/', ChangePasswordView.as_view(),
         name='auth_change_password'),
    # SCA22 — console fondateur des tenants (staff-only, sans billing).
    path('auth/console/tenants/', TenantConsoleListView.as_view(),
         name='auth_console_tenants'),
    path('auth/console/tenants/<int:pk>/statut/',
         TenantConsoleStatutView.as_view(), name='auth_console_tenant_statut'),
    path('auth/console/tenants/<int:pk>/note/',
         TenantConsoleNoteView.as_view(), name='auth_console_tenant_note'),
    # N100(b) — création administrée d'un tenant depuis la console fondateur.
    path('auth/console/tenants/creer/', TenantConsoleCreateView.as_view(),
         name='auth_console_tenant_creer'),
    # NTDMO25 — wizard « Créer ma société de démonstration » (3 étapes).
    path('auth/demo-wizard/', DemoWizardCreateView.as_view(),
         name='auth_demo_wizard'),
    path('auth/demo-wizard/statut/', DemoWizardStatusView.as_view(),
         name='auth_demo_wizard_statut'),
    # N101(b) — le dépôt PUBLIC d'une demande d'inscription
    # (`auth/signup-demande/`) est monté dans l'urlconf RACINE : sa vue vit
    # dans `apps.adminops` (une demande n'est pas un compte — la surface
    # d'authentification reste minimale), et cette app de FONDATION ne doit pas
    # importer une app satellite. La composition inter-apps est le rôle de
    # l'urlconf racine.
    path('', include(router.urls)),
]
