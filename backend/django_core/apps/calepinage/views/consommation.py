"""CAL149 — la porte des PROFILS TYPES de consommation de la société.

FORME D'URL (CAL233) : ``/api/django/calepinage/parametres/profils-types/``.
Ce n'est pas une seconde famille d'URL pour l'objet métier — aucun
identifiant de calepinage n'y entre : c'est un RÉGLAGE société, servi sous le
préfixe ``parametres`` comme la suggestion de pente (CAL237).

* ``GET`` — les profils SAISIS par la société, puis les profils de repli
  ÉTIQUETÉS « hypothèse interne » (jamais présentés comme des mesures).
* ``PUT`` — remplace les profils saisis. La société vient TOUJOURS de
  ``request.user``, jamais d'un corps de requête ; un refus est rendu 400 en
  NOMMANT le champ fautif (règle fondateur du 08/09/2026).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import CAL_GERER, CAL_VOIR
from ..serializers_conso import (
    ProfilsTypesEcritureSerializer, ProfilsTypesSerializer,
)
from ..services.profils_types import (
    ProfilInvalide, enregistrer_profils, profils_de_societe,
)

__all__ = ['ProfilsTypesView']


class ProfilsTypesView(APIView):
    """Les profils types de consommation de la société de l'appelant."""

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    @extend_schema(responses={200: ProfilsTypesSerializer})
    def get(self, request, *args, **kwargs):
        profils = profils_de_societe(getattr(request.user, 'company', None))
        return Response({'profils': profils})

    @extend_schema(request=ProfilsTypesEcritureSerializer,
                   responses={200: ProfilsTypesSerializer})
    def put(self, request, *args, **kwargs):
        corps = request.data if isinstance(request.data, dict) else {}
        try:
            profils = enregistrer_profils(
                getattr(request.user, 'company', None),
                corps.get('profils'),
                utilisateur=request.user)
        except ProfilInvalide as refus:
            return Response({refus.champ or 'profils': [str(refus)]},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'profils': profils})
