"""CAL191 — la vue ``GET /calepinages/<pk>/dossiers-reglementaires/``.

Elle sert MOT POUR MOT le contrat ``contract_samples/
dossiers_reglementaires.json`` (CAL247), que l'écran des dossiers (CAL196)
consomme : liste des dossiers disponibles pour le PAYS de la société, état
pièce par pièce, champs « à compléter » VENANT DU SERVEUR, et le message qui
dit quoi déposer quand la société n'a aucun gabarit.

Même forme que ``views/equipements.py`` (CAL243) : le code vit dans son
propre fichier et l'action est RATTACHÉE au ``CalepinageViewSet`` par une
affectation d'attribut de classe, depuis un import d'``urls.py`` exécuté
AVANT ``router.register`` — deux lanes travaillent en parallèle sur
``views/calepinages.py``, y ajouter une méthode garantirait un conflit.

Lecture PURE : aucune écriture, aucun dossier créé au passage (un GET qui
crée une ligne en base est un GET qui ment).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services.reglementaire import dossiers_du_calepinage
from .calepinages import CalepinageViewSet

__all__ = ['dossiers_reglementaires']


def _forme():
    """YAPIC6/PACT7 — la forme DÉCLARÉE, tirée du contrat CAL247."""
    return inline_serializer('CalepinageDossiersReglementaires', {
        'calepinage': serializers.IntegerField(),
        'pays': serializers.CharField(allow_null=True),
        'gabarits_deposes': serializers.IntegerField(),
        'message_aucun_gabarit': serializers.CharField(allow_null=True),
        'dossiers': serializers.ListField(child=serializers.DictField()),
    })


@extend_schema(responses={200: _forme()})
@action(detail=True, methods=['get'], url_path='dossiers-reglementaires',
        permission_classes=[PeutVoirCalepinage])
def dossiers_reglementaires(self, request, pk=None):
    """CAL191 — les dossiers réglementaires du calepinage (contrat CAL247)."""
    return Response(dossiers_du_calepinage(self.get_object()))


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.dossiers_reglementaires = dossiers_reglementaires
