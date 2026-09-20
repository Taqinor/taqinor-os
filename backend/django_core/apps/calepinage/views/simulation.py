"""Les ``@action`` de SIMULATION du calepinage — CAL139 (pertes sourcées).

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
----------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243) et ``views/export_csv.py``
(CAL144) : d'autres lanes ``backend/calepinage-*`` écrivent dans
``views/calepinages.py``. L'action vit donc dans SON fichier et est RATTACHÉE
au ``CalepinageViewSet`` par affectation d'attribut de classe, avec une seule
ligne d'import additive dans ``urls.py`` — qui doit s'exécuter AVANT
``router.register`` pour que le routeur la découvre.

UNE SEULE FORME D'URL (CAL233) : ces actions sont servies sous
``/api/django/calepinage/calepinages/<pk>/…``, comme tout le reste de l'objet
métier. La société vient du serveur (``get_object()`` borné par le queryset du
viewset : un calepinage d'une autre société est INTROUVABLE, jamais
« interdit »), et chaque action déclare SA garde.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..serializers_pertes import (
    PertesCalepinageSerializer, PostesDePertesSerializer,
)
from ..services.pertes import CATALOGUE, PertesInvalides, postes_du_calepinage
# Renommé à l'import : l'ACTION doit s'appeler ``enregistrer_pertes`` (le
# routeur DRF fige le nom de la méthode AU MOMENT de la décoration, dans
# ``MethodMapper`` — le renommer après coup ne changerait rien), donc le
# service ne peut pas garder ce nom ici. Même patron que ``views/export_csv``.
from ..services.pertes import enregistrer_pertes as persister_pertes
from .calepinages import CalepinageViewSet

__all__ = ['enregistrer_pertes', 'pertes', 'publication_des_pertes']


def publication_des_pertes(calepinage):
    """Le bloc publié : les postes, leur somme, et le catalogue de référence.

    ``total_pct`` est la somme RÉELLEMENT additionnée — la même que celle qui
    partira dans la requête PVGIS (CAL238). Aucun poste n'est complété : une
    liste vide reste vide, et ``simulable`` dit pourquoi aucune production ne
    peut être demandée.
    """
    postes = postes_du_calepinage(calepinage)
    total = sum(poste['pct'] for poste in postes)
    return {
        'calepinage': calepinage.pk,
        'pertes': postes,
        'total_pct': round(total, 3) if postes else None,
        'postes_non_sources': [poste['poste'] for poste in postes
                               if poste['source'] is None],
        'simulable': bool(postes),
        'motif_non_simulable': (
            '' if postes else
            "Aucun poste de perte n'est renseigné : le module passe TOUJOURS "
            'à PVGIS la somme explicite de ses postes et ne suppose jamais '
            'une perte par défaut.'),
        'catalogue': [dict(entree) for entree in CATALOGUE],
    }


@extend_schema(responses={200: PertesCalepinageSerializer})
@action(detail=True, methods=['get'], url_path='pertes',
        permission_classes=[PeutVoirCalepinage])
def pertes(self, request, pk=None):
    """CAL139 — ``GET /calepinages/<pk>/pertes/`` : les postes et leur somme.

    Lecture PURE. Le catalogue de référence accompagne la réponse pour que
    l'écran puisse proposer les postes PVsyst sans en inventer la valeur.
    """
    return Response(publication_des_pertes(self.get_object()))


@extend_schema(request=PostesDePertesSerializer,
               responses={200: PertesCalepinageSerializer})
@action(detail=True, methods=['post'], url_path='enregistrer-pertes',
        permission_classes=[PeutGererCalepinage])
def enregistrer_pertes(self, request, pk=None):
    """CAL139 — ``POST /calepinages/<pk>/enregistrer-pertes/``.

    Le corps porte ``{pertes: [{poste, libelle, pct, source, mensuel}]}``.
    Un refus est rendu 400 EN NOMMANT le poste fautif (règle fondateur du
    08/09/2026 : jamais un « non enregistré » générique).
    """
    calepinage = self.get_object()
    corps = request.data if isinstance(request.data, dict) else {}
    try:
        persister_pertes(calepinage, corps.get('pertes'))
    except PertesInvalides as refus:
        return Response({refus.champ or 'pertes': [str(refus)]},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(publication_des_pertes(calepinage))


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.pertes = pertes
CalepinageViewSet.enregistrer_pertes = enregistrer_pertes
