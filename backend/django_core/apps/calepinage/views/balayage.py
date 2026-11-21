"""ACAL468 — ``POST /calepinages/<pk>/balayage/`` : lance le balayage d'un pan.

Contrat ``contract_samples/calepinage_balayage.json`` (ACAL388). Greffée sur
``CalepinageViewSet`` par affectation d'attribut de classe (import en fin de
``views/rattachements.py``). La société vient du serveur (``get_object()``).

* **400** — la FORME du corps viole le schéma publié, EN NOMMANT le champ
  (axe inconnu, nombre attendu, pas ≤ 0, aucun axe…) ;
* **409** — refus nommé que le schéma ne peut pas dire : il tient au DOCUMENT
  (pas de conception, pan introuvable, pan à pente imposée par le toit,
  façade, est-ouest) ou à une contrainte croisée (min > max, bornes de l'axe,
  trop de points pour le cache PVGIS, axe répété) ; ou le calepinage ne se
  simule pas (mode météo, pan équipé, épingle…), mêmes refus que ``simuler/``
  (api-fuzz #1512 : une requête conforme au schéma n'est jamais un 400) ;
* **202** — le travail est parti en tâche de fond (kind ``calepinage``,
  ``nature`` = ``balayage``), à suivre sur ``moteur/resultat/<job_id>/``.

Rien n'est écrit au calepinage, aucun verrou n'est pris : le balayage ne
modifie que des COPIES du document.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE

from ..permissions import PeutGererCalepinage
from ..services.balayage import (
    AXES_PRIS_EN_CHARGE, BalayageInvalide, valider_demande,
)
from ..services.simulation import (
    SimulationRefusee, construire_contexte, fichier_meteo_depose,
    verifier_simulable,
)
from .calepinages import CalepinageViewSet

__all__ = ['accuse_de_balayage', 'balayage']


def accuse_de_balayage(job):
    """Le 202 du balayage — clé pour clé l'accusé de la simulation, avec
    ``nature`` = ``balayage`` (contrat ``calepinage_balayage.json``)."""
    from ..tasks import NATURE_BALAYAGE

    return {
        'job_id': job.pk,
        'kind': job.kind,
        'nature': NATURE_BALAYAGE,
        'statut': job.statut,
        'progress_pct': job.progress_pct,
        'message_erreur': job.message_erreur or '',
        'resultat': None,
        'detail': ('Balayage lancé en tâche de fond : suivez-le sur '
                   '/api/django/calepinage/moteur/resultat/%s/.' % job.pk),
    }


#: La forme EXACTE d'un axe, publiée en ``x-corps-resserre`` (aucun composant
#: ne change) : ce que ``valider_demande`` refuse en 400 (``forme``).
_AXES_RESSERRES = {EXTENSION_CORPS_RESSERRE: {'properties': {'axes': {
    'type': 'array', 'minItems': 1, 'items': {
        'type': 'object', 'required': ['nom', 'min', 'max', 'pas'],
        'properties': {
            'nom': {'type': 'string', 'enum': list(AXES_PRIS_EN_CHARGE)},
            'min': {'type': 'number'}, 'max': {'type': 'number'},
            'pas': {'type': 'number', 'minimum': 0,
                    'exclusiveMinimum': True}}}}}}}


@extend_schema(
    extensions=_AXES_RESSERRES,
    request=inline_serializer('CalepinageBalayageCorps', {
        'pan': serializers.IntegerField(),
        'axes': serializers.ListField(child=serializers.DictField())}),
    responses={202: inline_serializer('CalepinageBalayageAccuse', {
        'job_id': serializers.IntegerField(),
        'kind': serializers.CharField(),
        'nature': serializers.CharField(),
        'statut': serializers.CharField(),
        'progress_pct': serializers.IntegerField(),
        'message_erreur': serializers.CharField(allow_blank=True),
        'resultat': serializers.DictField(allow_null=True),
        'detail': serializers.CharField()})})
@action(detail=True, methods=['post'], url_path='balayage',
        permission_classes=[PeutGererCalepinage],
        parser_classes=[JSONParser])
def balayage(self, request, pk=None):
    """ACAL468 — ``POST /calepinages/<pk>/balayage/`` : le balayage
    inclinaison × azimut d'un pan libre, en tâche de fond."""
    from core.jobs import submit

    from ..tasks import NATURE_BALAYAGE, balayer_calepinage

    calepinage = self.get_object()  # borné société par get_queryset
    corps = request.data if isinstance(request.data, dict) else {}
    try:
        valider_demande(calepinage.roof_layout, corps)
    except BalayageInvalide as refus:
        return Response({refus.champ or 'balayage': [str(refus)]},
                        status=(status.HTTP_400_BAD_REQUEST if refus.forme
                                else status.HTTP_409_CONFLICT))
    # Les refus nommés de la simulation, AVANT la file : une tâche vouée à
    # l'échec coûterait un worker pour rien.
    try:
        contexte, meta = construire_contexte(calepinage)
        verifier_simulable(contexte, meta,
                           fichier_depose=fichier_meteo_depose(calepinage))
    except SimulationRefusee as refus:
        return Response({refus.champ or 'simulation': [refus.motif]},
                        status=status.HTTP_409_CONFLICT)
    from ..tasks import KIND_CALEPINAGE

    job = submit(KIND_CALEPINAGE, balayer_calepinage,
                 company=calepinage.company, user=request.user,
                 calepinage_id=calepinage.pk, corps={
                     'pan': corps.get('pan'), 'axes': corps.get('axes')},
                 nature=NATURE_BALAYAGE)
    return Response(accuse_de_balayage(job), status=status.HTTP_202_ACCEPTED)


CalepinageViewSet.balayage = balayage
