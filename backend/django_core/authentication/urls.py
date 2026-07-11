from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    RegisterCompanyView,
    UserViewSet,
    CompanyViewSet,
    MeView,
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
from .views_console import (
    TenantConsoleListView,
    TenantConsoleStatutView,
    TenantConsoleNoteView,
)

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
    path('', include(router.urls)),
]
