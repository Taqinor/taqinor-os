"""Routes de GOUVERNANCE IA — montées sous ``/api/django/ai-governance/``.

Distinctes des routes ``/api/django/ai/`` (les copilotes, utilisables par tout
collaborateur) : ici vivent les surfaces d'ADMINISTRATION de l'IA — journal
d'usage et coûts, budgets, état des capacités. Elles sont réservées au palier
Administrateur/Directeur.
"""
from django.urls import path

from .views import UsageView

urlpatterns = [
    # NTAI1 — agrégats d'usage & coût IA (par jour / feature / fournisseur).
    path('usage/', UsageView.as_view(), name='ai-governance-usage'),
]
