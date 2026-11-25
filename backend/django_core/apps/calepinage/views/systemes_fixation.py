"""ACAL558 — le catalogue des systèmes de fixation de la société, en HTTP.

Deux ``@action(detail=False)`` du viewset pivot (CAL233 : une seule forme
d'URL), rattachées par ``views/rattachements.py`` — ``urls.py`` n'est pas
touché :

* ``GET``/``POST calepinages/systemes-fixation/`` → ``{systemes}`` / 201
  ``{systeme}`` ;
* ``GET``/``PATCH``/``DELETE calepinages/systemes-fixation/<id>/`` →
  ``{systeme}`` / 204.

Contrat : ``contract_samples/calepinage_systemes_fixation.json`` (ACAL557).
Garde PAR MÉTHODE : lire = ``calepinage_voir``, écrire = ``calepinage_gerer``
(``PeutLireOuEcrireCalepinage``, en cumul avec ``ScopedPermission``). La
société est TOUJOURS celle de l'appelant ; un système d'une autre société est
INTROUVABLE (404), jamais « interdit ». Supprimer un système laisse les
calepinages qui le portaient sans choix (``on_delete=SET_NULL``, ACAL81).
Code métier : ``services/systemes_fixation.py``.
"""
from __future__ import annotations

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import (
    OpenApiResponse, extend_schema, extend_schema_field, inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.champs_stricts import MOTIF_SANS_NUL
from core.parseurs import PARSEURS_JSON

from ..models import ComposantFixation, SystemeFixation
from ..permissions import PeutLireOuEcrireCalepinage, exiger_droit_reglages_societe
from ..serializers import forme_du_contrat, forme_reponse
from ..services.catalogue_fixation import (
    BASES, CLES_REGLE, COUVERTURES, PREFIXE_ROLE, systeme_de_societe,
)
from ..services.controles_pose import CHAMPS_MM
from ..services.systemes_fixation import (
    SystemeRefuse, creer_systeme, liste_des_systemes, modifier_systeme,
    systeme_publie,
)
from .calepinages import CalepinageViewSet

__all__ = ['systemes_fixation', 'systeme_fixation']

#: Un nombre STRICTEMENT positif, ou ``null`` tant qu'il n'est pas saisi.
_POSITIF = {'type': 'number', 'minimum': 0, 'exclusiveMinimum': True,
            'nullable': True}
_TEXTE_SANS_NUL = {'type': 'string', 'pattern': MOTIF_SANS_NUL}


# api-fuzz (PR #1522) — la règle publiée est CELLE de ``erreur_de_regle`` :
# vide (non saisie) ou ``{base, facteur?, diviseur?, libelle_*?}`` sans autre
# clé ; la déclaration seule, la lecture reste celle du service.
@extend_schema_field({'nullable': True, 'oneOf': [
    {'type': 'object', 'additionalProperties': False, 'maxProperties': 0},
    {'type': 'object', 'additionalProperties': False, 'required': ['base'],
     'properties': {
         'base': {'type': 'string', 'enum': list(BASES) + [
             PREFIXE_ROLE + role for role in ComposantFixation.Role.values]},
         'facteur': _POSITIF, 'diviseur': _POSITIF,
         'libelle_facteur': _TEXTE_SANS_NUL,
         'libelle_diviseur': _TEXTE_SANS_NUL}},
]})
class _ChampRegle(serializers.JSONField):
    """Déclaration de la règle de quantité (clés : ``CLES_REGLE``)."""


assert set(CLES_REGLE) == {'base', 'facteur', 'diviseur', 'libelle_facteur',
                           'libelle_diviseur'}


#: ACAL568 — les contrôles de pose : trois distances en mm (>= 0) et leur source
#: (``erreur_de_controles_pose`` : source obligatoire dès qu'une valeur est
#: saisie) ; ``{}`` = non déclarés. Déclaration seule, le service refuse.
_CONTROLES_POSE = {
    'type': 'object', 'additionalProperties': False,
    'properties': {**{cle: {'type': 'number', 'minimum': 0, 'nullable': True}
                      for cle in CHAMPS_MM}, 'source': _TEXTE_SANS_NUL},
    # api-fuzz (PR #1523) — la règle « source dès qu'une valeur est saisie »
    # est publiée : aucune distance (absente ou null), OU une source non blanche.
    'anyOf': [
        {'type': 'object', 'properties': {
            cle: {'nullable': True, 'enum': [None]} for cle in CHAMPS_MM}},
        {'type': 'object', 'required': ['source'], 'properties': {
            'source': {'type': 'string',
                       'pattern': r'^[^\u0000]*\S[^\u0000]*$'}}},
    ]}


@extend_schema_field(_CONTROLES_POSE)
class _ChampControlesPose(serializers.JSONField):
    """Déclaration des contrôles de pose (clés : ``CHAMPS_MM`` + source)."""


def _corps(nom, *, creation):
    """Le corps PUBLIÉ (déclaration seule : le service lit et refuse). À la
    création, code, libellé et provenance sont requis (``SystemeFixation.clean``) ;
    un PATCH ne porte que ce qui change."""
    composant = inline_serializer(f'{nom}Composant', {
        'role': serializers.ChoiceField(ComposantFixation.Role.choices),
        'libelle': serializers.CharField(max_length=160),
        'unite': serializers.CharField(max_length=12),
        'source': serializers.CharField(),
        'produit_id': serializers.IntegerField(
            required=False, allow_null=True, min_value=0,
            max_value=2147483647),
        'regle': _ChampRegle(required=False),
    })
    return inline_serializer(nom, {
        'code': serializers.RegexField(r'^[-a-zA-Z0-9_]+$', max_length=60,
                                       required=creation),
        'libelle': serializers.CharField(max_length=200, required=creation),
        'fabricant': serializers.CharField(max_length=120, required=False,
                                           allow_blank=True),
        'mode_pose': serializers.ChoiceField(SystemeFixation.ModePose.choices,
                                             required=False),
        'actif': serializers.BooleanField(required=False),
        'provenance': serializers.CharField(required=creation),
        # ACAL566 — les couvertures servies (liste de ``COUVERTURES``).
        'couvertures': serializers.ListField(
            child=serializers.ChoiceField([(c, c) for c in COUVERTURES]),
            required=False),
        'controles_pose': _ChampControlesPose(required=False),  # ACAL568
        'composants': serializers.ListField(child=composant, required=False),
    })


_CORPS_CREATION = _corps('CalepinageSystemeFixationCreation', creation=True)
_CORPS = _corps('CalepinageSystemeFixationCorps', creation=False)
_UN_SYSTEME = forme_reponse('CalepinageSystemeFixation', 'systeme')
_REFUS_400 = OpenApiResponse(description="Refus nommant chaque champ fautif "
                                         "({chemin: [message]}).")
_REFUS_409 = OpenApiResponse(description="Code déjà porté par un autre système "
                                         "de la société ({code: [message]}).")


class _SchemaListeSystemes(AutoSchema):
    """La liste et le détail ont les MÊMES jetons de chemin (``systeme_id``
    retiré) : drf-spectacular baptisait les deux GET ``…_retrieve`` (collision
    ENF11). La liste prend le mot ``list`` ; le préfixe de montage
    (``django_``/``v1_``) est gardé — jamais un operationId écrit en dur
    (voir ``core/openapi_operations.py``). Déclaration seule."""

    def get_operation_id(self):
        operation_id = super().get_operation_id()
        if self.method == 'GET' and operation_id.endswith('_retrieve'):
            return operation_id[:-len('_retrieve')] + '_list'
        return operation_id


def _company(request):
    return getattr(request.user, 'company', None)


@extend_schema(methods=['GET'], responses=forme_du_contrat(
    'CalepinageSystemesFixation', 'calepinage_systemes_fixation.json'))
@extend_schema(methods=['POST'], request=_CORPS_CREATION, responses={
    201: _UN_SYSTEME, 400: _REFUS_400, 409: _REFUS_409})
@action(detail=False, methods=['get', 'post'], url_path='systemes-fixation',
        url_name='systemes-fixation',
        permission_classes=[PeutLireOuEcrireCalepinage],
        parser_classes=PARSEURS_JSON, schema=_SchemaListeSystemes())
def systemes_fixation(self, request):
    """ACAL558 — lister ou créer un système (composants compris)."""
    company = _company(request)
    if request.method.lower() == 'get':
        return Response(liste_des_systemes(company))
    exiger_droit_reglages_societe(request.user)  # D-ACAL-104 — le catalogue de fixation est à la société
    try:
        systeme = creer_systeme(company, request.data)
    except SystemeRefuse as refus:
        return Response(refus.erreurs, status=refus.statut)
    return Response({'systeme': systeme}, status=status.HTTP_201_CREATED)


@extend_schema(methods=['GET'], responses=_UN_SYSTEME)
@extend_schema(methods=['PATCH'], request=_CORPS, responses={
    200: _UN_SYSTEME, 400: _REFUS_400, 409: _REFUS_409})
@extend_schema(methods=['DELETE'], request=None, responses={204: None})
@action(detail=False, methods=['get', 'patch', 'delete'],
        url_path=r'systemes-fixation/(?P<systeme_id>[0-9]+)',
        url_name='systeme-fixation',
        permission_classes=[PeutLireOuEcrireCalepinage],
        parser_classes=PARSEURS_JSON)
def systeme_fixation(self, request, systeme_id=None):
    """ACAL558 — lire, modifier (composants remplacés) ou supprimer."""
    if request.method.lower() != 'get':
        exiger_droit_reglages_societe(request.user)  # D-ACAL-104
    systeme = systeme_de_societe(_company(request), systeme_id)
    if systeme is None:
        return Response(
            {'detail': "Système de fixation introuvable dans votre société."},
            status=status.HTTP_404_NOT_FOUND)
    methode = request.method.lower()
    if methode == 'get':
        return Response({'systeme': systeme_publie(systeme)})
    if methode == 'delete':
        systeme.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    try:
        publie = modifier_systeme(systeme, request.data)
    except SystemeRefuse as refus:
        return Response(refus.erreurs, status=refus.statut)
    return Response({'systeme': publie})


# Le nom d'attribut est EXACTEMENT celui de la fonction (piège CALX7).
CalepinageViewSet.systemes_fixation = systemes_fixation
CalepinageViewSet.systeme_fixation = systeme_fixation
