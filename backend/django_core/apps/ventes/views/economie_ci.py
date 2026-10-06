"""CIQ210 — ``GET /api/django/ventes/devis/<pk>/economie-ci/`` (lecture seule).

Sert le bloc ``economie_ci`` INTERNE d'un devis commercial / industriel (avec
``vue_interne`` et ``alertes_internes``), forme du contrat
``contract_samples/economie_ci.json``. Le calcul vit dans
``apps/ventes/economie_ci.py`` (:func:`economie_ci_pour_devis`) ; le PDF et
/proposition lisent la MÊME fonction, passée par ``economie_ci_publique``.

Patron ``views/economie.py`` (CALX288) : action GREFFÉE au ``DevisViewSet``
par affectation d'attribut ; ``IsAnyRole`` ; ``get_object`` passe par le
queryset scopé (404 hors société, jamais 403) ; LECTURE SEULE — aucune
écriture, aucun statut changé (règle #4).
"""
from __future__ import annotations

from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

from ..economie_ci import SaisieEconomieCiInvalide, economie_ci_pour_devis
from ..economie_ci_view import refus_saisie
from .devis import DevisViewSet

__all__ = ['economie_ci']


# api-only: CIQ210 — lecture interne du bloc (contrat CIQ3) ; le PDF et
# /proposition le lisent côté serveur, l'écran C&I le branchera (D3).
@action(detail=True, methods=['get'], url_path='economie-ci',
        permission_classes=[IsAnyRole])
def economie_ci(self, request, pk=None):
    """CIQ210 — le bloc ``economie_ci`` du devis (contrat CIQ3), en lecture."""
    devis = self.get_object()
    try:
        bloc = economie_ci_pour_devis(devis, devis.company)
    except SaisieEconomieCiInvalide as refus:
        return refus_saisie(refus)
    return Response(bloc)


# Rattachement au viewset PIVOT — voir la docstring de ``views/economie.py``.
DevisViewSet.economie_ci = economie_ci
