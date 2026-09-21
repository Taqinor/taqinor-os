"""CAL246 — ``GET /calepinages/modeles/`` : les calepinages MARQUÉS modèle.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243) : d'AUTRES lanes
``backend/calepinage-*`` travaillent en ce moment sur ``views/calepinages.py``
(file-disjoint par construction du plan de lanes) — y ajouter une méthode
créerait un conflit de fusion garanti. L'action est donc posée ICI, sur son
propre fichier, puis RATTACHÉE au ``CalepinageViewSet`` par une ligne
d'import dans ``urls.py`` (affectation d'attribut de classe — le même effet
qu'une définition inline, sans toucher au corps de la classe).

LA BIBLIOTHÈQUE (CAL197-CAL200), EN DEUX ENDROITS — JAMAIS UNE TROISIÈME
FORME D'URL (CAL233)
--------------------------------------------------------------------------
* ``GET /api/django/calepinage/parametres/`` sert DÉJÀ les presets et le
  matériel favori (sections de ``ParametresCalepinage``, CAL45/CAL16) — ce
  module y AJOUTE ``kits`` (catalogue LU, jamais stocké : voir
  ``views/parametres.py``) ;
* ``GET /api/django/calepinage/calepinages/modeles/`` (CETTE action, sur le
  routeur DRF de l'objet métier — ``detail=False``, donc pas de second
  préfixe d'URL) sert les calepinages marqués MODÈLE (CAL199).

Lecture PURE, bornée société par ``get_queryset``/``self.request.user`` comme
toute autre action du viewset — écriture gardée par ``calepinage_gerer``
ailleurs (marquer/démarquer, action de ``services.modeles``).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..selectors import calepinage_detail
from ..serializers import CalepinageSerializer
from ..services.modeles import ModeleInvalide, calepinages_modeles
from ..services.modeles import creer_depuis_modele as service_creer
from ..services.modeles import demarquer_modele as service_demarquer
from ..services.modeles import marquer_modele as service_marquer
from .calepinages import CalepinageViewSet

__all__ = ['modeles', 'marquer_modele', 'demarquer_modele',
           'creer_depuis_modele']


@action(detail=False, methods=['get'], url_path='modeles',
        permission_classes=[PeutVoirCalepinage])
def modeles(self, request):
    """CAL199/CAL246 — les calepinages marqués « modèle » de la société.

    Lecture PURE, bornée société (``request.user.company`` — jamais un corps
    de requête)."""
    company = getattr(request.user, 'company', None)
    lignes = calepinages_modeles(company)
    return Response(CalepinageSerializer(lignes, many=True).data)


# ── CALX42 — LES TROIS PORTES D'ÉCRITURE DE LA BIBLIOTHÈQUE ────────────────
# ``services/modeles.py`` porte ``marquer_modele`` (:76), ``demarquer_modele``
# (:97) et ``creer_depuis_modele`` (:140), écrits et testés depuis CAL199 ;
# seule la LECTURE ``modeles`` était servie, et l'écran de bibliothèque se
# déclarait en lecture seule « faute de porte ». Les trois portes sont posées
# ICI, dans le module qui sert déjà la lecture — pas un module de plus, donc
# aucune ligne neuve dans ``views/rattachements.py`` (il importe déjà celui-ci).
# Aucun troisième chemin de copie n'est ouvert : ``creer_depuis_modele``
# appelle ``services.variantes.dupliquer`` (CAL14), comme sa docstring le dit.


def _corps(request):
    return request.data if isinstance(request.data, dict) else {}


def _identifiant(brut):
    """Un identifiant entier, ou ``None`` — jamais une valeur devinée."""
    if brut in (None, ''):
        return None
    try:
        return int(brut)
    except (TypeError, ValueError):
        return None


@action(detail=True, methods=['post'], url_path='marquer-modele',
        permission_classes=[PeutGererCalepinage])
def marquer_modele(self, request, pk=None):
    """CALX42 — pose le drapeau « modèle réutilisable » (idempotent)."""
    calepinage = self.get_object()  # borné société par get_queryset
    try:
        service_marquer(calepinage, user=request.user)
    except ModeleInvalide as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({'calepinage': calepinage.pk, 'modele': True})


@action(detail=True, methods=['post'], url_path='demarquer-modele',
        permission_classes=[PeutGererCalepinage])
def demarquer_modele(self, request, pk=None):
    """CALX42 — retire le drapeau « modèle » (idempotent)."""
    calepinage = self.get_object()  # borné société par get_queryset
    service_demarquer(calepinage, user=request.user)
    return Response({'calepinage': calepinage.pk, 'modele': False})


@action(detail=False, methods=['post'], url_path='creer-depuis-modele',
        permission_classes=[PeutGererCalepinage])
def creer_depuis_modele(self, request):
    """CALX42 — un calepinage NEUF, parti d'un modèle, sur un NOUVEAU
    rattachement.

    La société vient de ``request.user`` ; le modèle est résolu DANS cette
    société (introuvable ailleurs, jamais « interdit »). Le rattachement du
    modèle n'est jamais recopié : sans lead ni client fourni, le service
    refuse en nommant le champ.
    """
    corps = _corps(request)
    company = getattr(request.user, 'company', None)
    modele = calepinage_detail(_identifiant(corps.get('modele')), company)
    if modele is None:
        return Response({'modele': 'Modèle introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        copie = service_creer(
            modele, user=request.user,
            lead_id=_identifiant(corps.get('lead')),
            client_id=_identifiant(corps.get('client')),
            titre=str(corps.get('titre') or ''))
    except ModeleInvalide as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(CalepinageSerializer(copie).data,
                    status=status.HTTP_201_CREATED)


# Rattachement au viewset PIVOT — voir la docstring du module pour le
# pourquoi de cette forme plutôt qu'une méthode inline. Le nom d'attribut est
# EXACTEMENT celui de la fonction : DRF découvre l'action par
# ``get_extra_actions()`` et compare les deux.
CalepinageViewSet.modeles = modeles
CalepinageViewSet.marquer_modele = marquer_modele
CalepinageViewSet.demarquer_modele = demarquer_modele
CalepinageViewSet.creer_depuis_modele = creer_depuis_modele
