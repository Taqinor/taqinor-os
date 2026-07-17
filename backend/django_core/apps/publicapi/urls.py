"""Routes de GESTION (Paramètres) — clés API & webhooks (N89).

Montées sous /api/django/publicapi/. Distinct de l'API publique de données
(/api/public/) et des liens PDF tokenisés (/api/django/public/).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ApiKeyViewSet, WebhookViewSet, CatalogueView, DocsView, OcrToCrmView,
    ApiUsagePlanView, SandboxTryView,
)

router = DefaultRouter()
router.register(r'keys', ApiKeyViewSet, basename='apikey')
router.register(r'webhooks', WebhookViewSet, basename='webhook')

urlpatterns = [
    path('catalogue/', CatalogueView.as_view(), name='publicapi-catalogue'),
    # FG105 — référence statique FR de l'API publique (consultée depuis l'écran).
    path('docs/', DocsView.as_view(), name='publicapi-docs'),
    # FG106 — passerelle OCR → lead/devis brouillon (écriture via services cibles).
    path('ocr-to-crm/', OcrToCrmView.as_view(), name='publicapi-ocr-to-crm'),
    # NTAPI7 — plan d'API nommé (gratuit/pro/entreprise) de la société.
    path('plan/', ApiUsagePlanView.as_view(), name='publicapi-plan'),
    # NTAPI21 — « essayer » un endpoint depuis la console de docs (session
    # admin, jamais une clé brute côté client), scopé au bac à sable NTAPI27.
    path('sandbox/try/', SandboxTryView.as_view(), name='publicapi-sandbox-try'),
    path('', include(router.urls)),
]
