"""CALX109 — ``GET calepinages/<pk>/modules-disponibles/``.

LA PORTE DU CATALOGUE DE MODULES
---------------------------------
L'atelier 3D pose aujourd'hui un module unique, écrit en dur côté navigateur.
Cette action lui sert les modules que la société a RÉELLEMENT au catalogue,
avec les cotes de leur fiche technique, dans la forme exacte du catalogue
``modules[]`` du document v2 (CALX82) : l'atelier écrit l'entrée choisie sans
la traduire, et le pan la désigne par ``zones[].geometry.moduleId``.

Lecture PURE : aucune écriture, aucun statut touché, aucune conception
modifiée. La société vient de l'objet résolu par ``get_queryset`` (donc de
``request.user``), jamais d'un corps de requête — un calepinage d'une autre
société est INTROUVABLE, et son catalogue avec lui.

FORME DE GREFFE
---------------
Le code vit dans ce fichier et se rattache au ``CalepinageViewSet`` par
affectation d'attribut de classe, déclenchée par une ligne d'import ajoutée en
fin de ``views/rattachements.py`` (D-CALX 13). Le nom d'attribut est
EXACTEMENT celui de la fonction : DRF mappe par ``__name__``. Le service
s'appelle donc ``modules_disponibles_du_calepinage`` — deux noms distincts
pour deux rôles distincts, jamais une collision d'import qui casserait la
route en silence.
"""
from __future__ import annotations

from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services.modules_stock import modules_disponibles_du_calepinage

__all__ = ['modules_disponibles']


@action(detail=True, methods=['get'], url_path='modules-disponibles',
        permission_classes=[PeutVoirCalepinage])
def modules_disponibles(self, request, pk=None):
    """CALX109 — les fiches « module » de la société, cotes comprises."""
    from apps.stock.selectors import produits_modules_qs

    calepinage = self.get_object()
    produits = produits_modules_qs(getattr(calepinage, 'company', None))
    return Response(
        modules_disponibles_du_calepinage(calepinage, produits))


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

CalepinageViewSet.modules_disponibles = modules_disponibles
