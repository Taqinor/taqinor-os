import os
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from authentication.views import CustomTokenObtainPairView

_ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'api/django/admin/')

urlpatterns = [
    path(_ADMIN_URL, admin.site.urls),
    # JWT Auth endpoints
    path(
        'api/django/token/',
        CustomTokenObtainPairView.as_view(),
        name='token_obtain_pair',
    ),
    path(
        'api/django/token/refresh/',
        TokenRefreshView.as_view(),
        name='token_refresh',
    ),
    path(
        'api/django/token/verify/',
        TokenVerifyView.as_view(),
        name='token_verify',
    ),
    # App URLs
    path('api/django/', include('authentication.urls')),
    path('api/django/stock/', include('apps.stock.urls')),
    path('api/django/crm/', include('apps.crm.urls')),
    path('api/django/ventes/', include('apps.ventes.urls')),
    path('api/django/parametres/', include('apps.parametres.urls')),
    path('api/django/roles/', include('apps.roles.urls')),
    path('api/django/reporting/', include('apps.reporting.urls')),
    path('api/django/contact/', include('apps.contact.urls')),
    path('api/django/installations/', include('apps.installations.urls')),
    path('api/django/sav/', include('apps.sav.urls')),
    path('api/django/outillage/', include('apps.outillage.urls')),
    path('api/django/records/', include('apps.records.urls')),
    path('api/django/imports/', include('apps.dataimport.urls')),
    path('api/django/custom-fields/', include('apps.customfields.urls')),
    path('api/django/documents/', include('apps.documents.urls')),
    path('api/django/audit/', include('apps.audit.urls')),
    path('api/django/monitoring/', include('apps.monitoring.urls')),
    path('api/django/notifications/', include('apps.notifications.urls')),
    path('api/django/automation/', include('apps.automation.urls')),
    # Liens publics tokenisés (PDF client via WhatsApp) — sans login.
    path('api/django/public/', include('apps.ventes.public_urls')),
    # N89 — API publique REST par clé d'API (données read-only).
    path('api/public/', include('apps.publicapi.public_urls')),
    # N89 — gestion des clés API & webhooks (session admin, Paramètres).
    path('api/django/publicapi/', include('apps.publicapi.urls')),
]

# En production (DEBUG off + gunicorn), les statiques (admin Django) sont
# servis par Django lui-même derrière nginx — volume faible (UI interne),
# pas de dépendance supplémentaire. Activé explicitement par l'env.
if os.environ.get('DJANGO_SERVE_STATIC') == '1':
    from django.conf import settings
    from django.urls import re_path
    from django.views.static import serve as _static_serve

    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', _static_serve,
                {'document_root': settings.STATIC_ROOT}),
    ]
