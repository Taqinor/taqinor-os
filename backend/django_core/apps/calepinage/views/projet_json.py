"""CALX370 — ``POST /calepinages/import-projet/`` : réimporter un projet.

L'EXPORT N'EST PAS REDOUBLÉ. Le fichier réimporté est celui que sert
``GET /calepinages/<pk>/export-projet.json/`` (CALX312, ``views/documents.py``,
service ``services/export_projet.document_de_projet``) ; cette porte en est
l'inverse et vit dans le MÊME module de service
(``services/export_projet.importer_projet``) — aucun second module d'export.

CE QUE LA PORTE FAIT
--------------------
* corps : ``{projet: <le fichier>, lead: <id> | client: <id>, titre?,
  apercu?}`` — le rattachement désigne un lead OU un client de la société de
  l'APPELANT ; ceux du fichier appartiennent à la société de départ et ne
  sont jamais repris ;
* ``apercu: true`` valide TOUT le fichier et rend ce qui SERAIT écrit, sans
  rien écrire (l'écran le montre avant la confirmation explicite) ;
* sinon, un NOUVEAU calepinage est créé (201) par ``services/creation.py``,
  sa conception enregistrée par ``services/layout.py::enregistrer_layout``,
  ses postes de pertes et ses variantes par leurs services — jamais par un
  second chemin ;
* un refus est rendu 400 en NOMMANT le chemin du champ fautif
  (``format_version``, ``roof_layout.zones.0.vertices``,
  ``variantes[1].nom``…) — règle fondateur du 08/09/2026.

La société et l'auteur viennent TOUJOURS du serveur (``request.user``) :
aucun identifiant de société ni d'utilisateur n'est lu du fichier ni du corps.
Forme : ``contract_samples/calepinage_projet_json.json``.
"""
from __future__ import annotations

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from core.champs_stricts import BooleenStrict, ChaineStricte

from ..permissions import PeutGererCalepinage
from ..serializers import corps_obligatoire
from ..services.export_projet import (
    FORMATS_IMPORTABLES, ImportProjetRefuse, importer_projet,
)
from .calepinages import CalepinageViewSet

__all__ = ['import_projet']


#: La forme DÉCLARÉE de la réponse (jamais un « type: object » vide —
#: check_openapi_shapes, R1). Contrat : ``calepinage_projet_json.json``.
IMPORT_PROJET_SCHEMA = inline_serializer('CalepinageImportProjet', {
    'calepinage': serializers.IntegerField(allow_null=True),
    'titre': serializers.CharField(allow_blank=True),
    'format_version': serializers.IntegerField(),
    'ecrit': serializers.BooleanField(),
    'modules': serializers.IntegerField(allow_null=True),
    'postes_pertes': serializers.IntegerField(),
    'variantes': serializers.IntegerField(),
    'variante_retenue': serializers.CharField(allow_null=True),
    'repris': serializers.ListField(child=serializers.CharField()),
    'ignores': serializers.ListField(child=serializers.DictField()),
    'avertissements': serializers.ListField(child=serializers.CharField()),
    # ACAL243 — le chemin d'écran du calepinage importé (null à l'aperçu).
    'ouvrir': serializers.CharField(allow_null=True),
})


#: Plus grand identifiant d'une clé primaire entière (``AutoField`` PostgreSQL,
#: entier 32 bits) : au-delà, la requête ne peut désigner aucune ligne.
ID_MAX = 2_147_483_647


# ERR-ENF11-FUZZ-CALEPINAGE (w4) — le corps de ``import-projet``, UN seul
# prédicat publié ET appliqué : un fichier OBJET portant une ``format_version``
# lue par ce serveur ; ``apercu`` un vrai booléen ; EXACTEMENT un de ``lead`` /
# ``client`` (entiers 1..2^31-1) ; ``titre`` d'au plus 200 signes (la colonne).
# Le contenu du fichier (conception, postes, variantes, coûts, saisies) et
# l'existence du lead / client sont des faits que ce schéma ne peut pas dire :
# 409 / 404 (``ImportProjetRefuse.statut``). (Commentaire et non docstring :
# elle fuiterait dans la description OpenAPI.)
class ProjetFichierSerializer(serializers.Serializer):
    format_version = serializers.IntegerField(
        min_value=min(FORMATS_IMPORTABLES), max_value=max(FORMATS_IMPORTABLES))


class ImportProjetChampsSerializer(serializers.Serializer):
    apercu = BooleenStrict(required=False)
    lead = serializers.IntegerField(required=False, min_value=1,
                                    max_value=ID_MAX)
    client = serializers.IntegerField(required=False, min_value=1,
                                      max_value=ID_MAX)
    titre = ChaineStricte(required=False, allow_blank=True, max_length=200,
                          trim_whitespace=False)

    def validate(self, attrs):
        if ('lead' in attrs) == ('client' in attrs):
            raise serializers.ValidationError({
                'lead': ["Indiquez le lead OU le client de votre société "
                         "auquel rattacher le projet importé (un seul des "
                         "deux)."]})
        return attrs


class CalepinageImportProjetCorpsSerializer(ImportProjetChampsSerializer):
    projet = ProjetFichierSerializer()


class _RattachementUniquePublie(OpenApiSerializerExtension):
    """« Exactement un de lead / client » PUBLIÉ (``oneOf`` de deux
    ``required``) : sans cela ``{projet}`` seul, ou les deux ensemble, étaient
    des corps « conformes » refusés en 400."""
    target_class = CalepinageImportProjetCorpsSerializer

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        return {**schema, 'oneOf': [{'required': ['lead']},
                                    {'required': ['client']}]}


@extend_schema(
    request=CalepinageImportProjetCorpsSerializer,
    responses={200: IMPORT_PROJET_SCHEMA, 201: IMPORT_PROJET_SCHEMA})
@corps_obligatoire
@action(detail=False, methods=['post'], url_path='import-projet',
        permission_classes=[PeutGererCalepinage],
        parser_classes=[JSONParser])  # ``projet`` est un objet JSON imbriqué
def import_projet(self, request):
    """CALX370 — réimporte le fichier de projet (nouveau calepinage)."""
    donnees = request.data if isinstance(request.data, dict) else {}
    # Le fichier lui-même est jugé par le service (``projet`` non objet,
    # version inconnue : 400 nommé, motif français) ; ici, la forme du reste.
    champs = ImportProjetChampsSerializer(data=donnees)
    champs.is_valid(raise_exception=True)
    corps = champs.validated_data
    apercu = corps.get('apercu') is True
    try:
        resume = importer_projet(
            donnees.get('projet'), getattr(request.user, 'company', None),
            user=request.user,
            lead_id=corps.get('lead'), client_id=corps.get('client'),
            titre=corps.get('titre') or '',
            apercu=apercu)
    except ImportProjetRefuse as refus:
        return Response({refus.champ or 'projet': str(refus)},
                        status=refus.statut)
    return Response(resume, status=(status.HTTP_200_OK if apercu
                                    else status.HTTP_201_CREATED))


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.import_projet = import_projet
