"""Routes de GOUVERNANCE IA — montées sous ``/api/django/ai-governance/``.

Distinctes des routes ``/api/django/ai/`` (les copilotes, utilisables par tout
collaborateur) : ici vivent les surfaces d'ADMINISTRATION de l'IA — journal
d'usage et coûts, budgets, état des capacités. Elles sont réservées au palier
Administrateur/Directeur.
"""
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CapabilitiesView, UsageView
from .viewsets import (AiFeatureToggleViewSet, LlmBudgetViewSet,
                       PromptTemplateViewSet)

# SimpleRouter (et non DefaultRouter) : ce préfixe ne doit pas gagner une vue
# « api-root » qu'il n'avait pas.
router = SimpleRouter()
# NTAI2 — budget IA mensuel + seuil d'alerte (admin uniquement).
router.register(r'budgets', LlmBudgetViewSet, basename='ai-budget')
# NTAI5 — bibliothèque de prompts éditables (admin uniquement).
router.register(r'prompt-templates', PromptTemplateViewSet,
                basename='ai-prompt-template')
# NTAI7 — consentement IA par feature (admin uniquement ; défaut = actif).
router.register(r'feature-toggles', AiFeatureToggleViewSet,
                basename='ai-feature-toggle')

urlpatterns = [
    # NTAI1 — agrégats d'usage & coût IA (par jour / feature / fournisseur).
    path('usage/', UsageView.as_view(), name='ai-governance-usage'),
    # NTAI6 — état réel de chaque capacité IA (aucun secret exposé).
    path('capabilities/', CapabilitiesView.as_view(),
         name='ai-governance-capabilities'),
    path('', include(router.urls)),
]
