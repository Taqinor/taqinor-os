"""Routes de GESTION (Paramètres) — clés API & webhooks (N89).

Montées sous /api/django/publicapi/. Distinct de l'API publique de données
(/api/public/) et des liens PDF tokenisés (/api/django/public/).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ApiKeyViewSet, WebhookViewSet, CatalogueView, DocsView

router = DefaultRouter()
router.register(r'keys', ApiKeyViewSet, basename='apikey')
router.register(r'webhooks', WebhookViewSet, basename='webhook')

urlpatterns = [
    path('catalogue/', CatalogueView.as_view(), name='publicapi-catalogue'),
    # FG105 — référence statique FR de l'API publique (consultée depuis l'écran).
    path('docs/', DocsView.as_view(), name='publicapi-docs'),
    path('', include(router.urls)),
]
