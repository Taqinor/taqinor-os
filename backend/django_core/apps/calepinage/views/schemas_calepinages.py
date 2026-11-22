"""Les formes de corps / de réponse OpenAPI de ``views/calepinages.py`` (sorties du fichier : il ne grossit pas)."""
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, PolymorphicProxySerializer, inline_serializer,
)
from rest_framework import serializers as drf_serializers

from core.champs_stricts import ChaineStricte
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE, MOTIF_NON_BLANC

from ..serializers import (
    ChampsPersonnalisesField, ContraintesSiteCreationField, forme_du_contrat,
)
from ..services.layout import CHAMPS_SECTION_ZONE, CLES_SECTION_RACINE

_CREATION_COMMUNE = {
    'titre': ChaineStricte(required=False, allow_blank=True, max_length=200),
    'responsable': drf_serializers.IntegerField(required=False,
                                                allow_null=True),
    'contraintes_site': ContraintesSiteCreationField(required=False,
                                                     allow_null=True),
    'custom_data': ChampsPersonnalisesField(required=False, allow_null=True),
}
#: Un calepinage se crée par un LEAD ou par un CLIENT (jamais sans l'un des
#: deux : 400 ``client``) — deux formes, ``oneOf``.
CORPS_CREATION = PolymorphicProxySerializer(
    component_name='CalepinageCreation', resource_type_field_name=None,
    serializers=[
        inline_serializer('CalepinageCreationParLead', {
            'lead': drf_serializers.IntegerField(), **_CREATION_COMMUNE}),
        inline_serializer('CalepinageCreationParClient', {
            'client': drf_serializers.IntegerField(), **_CREATION_COMMUNE}),
    ])
VERSION_LIGNE = inline_serializer('CalepinageVersionLigne', {
    'id': drf_serializers.IntegerField(),
    'libelle': drf_serializers.CharField(allow_blank=True),
    'layout_hash': drf_serializers.CharField(allow_null=True),
    'cree_le': drf_serializers.CharField(allow_null=True),
    'cree_par': drf_serializers.JSONField(required=False, allow_null=True),
    'a_un_resultat': drf_serializers.BooleanField(),
}, many=True)
PUBLICATION_DEVIS = forme_du_contrat(
    'CalepinagePublicationDevis', 'calepinage_publication.json')
REFUS_VENTES = OpenApiResponse(
    description="Refus du serveur ventes (pré-vol, catalogue invalide) : sa "
                "charge, mot pour mot.")
#: ACAL316 — le 428 que sert une écriture complète sans jeton If-Match :
#: DOCUMENTÉ (api-fuzz du 14/10/2026 : « code HTTP non documenté »).
REPONSE_JETON_MANQUANT = OpenApiResponse(
    response=inline_serializer('CalepinageJetonManquant', {
        'detail': drf_serializers.CharField()}),
    description="Jeton de version (If-Match) absent ou blanc : rien n'est "
                "écrit ; recharger la conception (GET ``layout``) puis "
                "renvoyer son ``empreinte_document``.")
#: OBLIGATOIRE et non blanc (``pattern`` = au moins un caractère visible, la
#: règle exacte de ``_jeton_if_match``) : la précondition fait partie du
#: contrat (api-fuzz du 14/10/2026 : « requête conforme rejetée » sur un
#: en-tête vide). Un jeton périmé reste conforme et répond 409.
PARAM_IF_MATCH = OpenApiParameter(
    'If-Match', {'type': 'string', 'pattern': MOTIF_NON_BLANC},
    OpenApiParameter.HEADER, required=True,
    description="Empreinte « document » lue avec la conception (GET "
                "``layout``) ; l'ETag vide ``\"\"`` pour un document vide. "
                "Exigé pour écrire : absent ou blanc, 428 et rien n'est écrit, "
                "avant tout contrôle d'état (calepinage archivé) ; périmé, "
                "409.")
#: ``_corps_de_layout`` : un objet NON VIDE ; une enveloppe seule
#: (``{"layout": …}`` / ``{"roof_layout": …}``) porte un objet non vide. Un
#: ``{}`` ou ``{"layout": null}`` était « conforme » puis refusé en 400.
CORPS_LAYOUT_RESSERRE = {EXTENSION_CORPS_RESSERRE: {
    'type': 'object', 'minProperties': 1,
    'properties': {
        cle: {'type': 'object', 'minProperties': 1}
        for cle in ('roof_layout', 'layout')}}}
#: ERR-ENF11-FUZZ-CALEPINAGE — ``layout/section`` : une clé RACINE de la liste
#: blanche (valeur libre), ou ``zones`` avec ``zone_id`` et des ``champs`` pris
#: dans ``CHAMPS_SECTION_ZONE`` (``services.layout.enregistrer_section``).
SECTION_RESSERRE = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'properties': {'cle': {'enum': list(CLES_SECTION_RACINE)}}},
    {'required': ['zone_id', 'champs'], 'properties': {
        'cle': {'enum': ['zones']},
        'zone_id': {'type': 'string', 'minLength': 1},
        'champs': {'type': 'object', 'minProperties': 1,
                   'additionalProperties': False,
                   'properties': {c: {} for c in CHAMPS_SECTION_ZONE}}}},
]}}
