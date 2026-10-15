"""N97 — Export configurable & sauvegarde des données de la société.

Trois endpoints, tous réservés au rôle administrateur (``IsAdminRole``) et
TOUJOURS filtrés par la société de l'utilisateur connecté — jamais une autre :

* ``GET  /api/django/imports/export-objects/``  liste des objets + formats
* ``POST /api/django/imports/export-object/``   export d'UN objet -> fichier
* ``POST /api/django/imports/sauvegarde/``       bundle ZIP des objets choisis

Rien n'est persisté : les fichiers sont générés à la demande et streamés
(HttpResponse). Le prix d'achat (``Produit.prix_achat``) n'est jamais inclus
(exclu en amont par ``export_registry``).

Ce module est DISTINCT de l'import (``views.py`` / ``exports_view.py``) : il
s'ajoute à côté sans rien remplacer.
"""
import datetime

from django.http import HttpResponse
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes)
from rest_framework.response import Response

from authentication.permissions import IsAdminRole
from core.champs_stricts import ChaineStricte
from core.parseurs import PARSEURS_JSON, corps_valide

from .schema_fields import champ_choix
from .exporters import (
    DEFAULT_FORMAT, FORMATS, backup_filename, build_backup_zip,
    export_bytes, filename_for,
)
from .export_registry import (
    DEFAULT_OBJECTS, REGISTRY, available_objects,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers


_FICHIERS_EXPORT = {
    (200, FORMATS[k][1]): OpenApiTypes.BINARY for k in FORMATS}


def _company_of(user):
    """Société de l'utilisateur, ou None si non rattaché (superuser nu)."""
    return user.company if user.company_id else None


def _clean_objects(raw):
    """Clés demandées (DÉJÀ validées par ``SauvegardeRequete`` : toutes
    connues), dans l'ordre du registre.

    Liste vide / absente -> défaut (tous les objets).
    """
    if not raw:
        return list(DEFAULT_OBJECTS)
    requested = set(raw)
    keys = [k for k in REGISTRY if k in requested]
    return keys or list(DEFAULT_OBJECTS)


#: ENF11 (api-fuzz) — « format absent » ≠ « format: null » : seule l'ABSENCE de
#: la clé retombe sur le défaut ; `null` (type faux) est refusé comme tout type faux.
_ABSENT = object()


def _clean_format(raw, repli=False):
    """Format demandé ; absent (None) → défaut. ENF11 — une valeur FOURNIE
    mais hors ``FORMATS`` (chaîne vide, type faux) est refusée (``None``) au
    lieu d'être remplacée en silence par le défaut. ``repli`` : export d'UN
    objet, où une chaîne inconnue retombe sur le défaut (comportement
    documenté et déclaré) ; un type faux reste refusé."""
    if raw is _ABSENT:
        return DEFAULT_FORMAT
    if not isinstance(raw, str):
        return None
    fmt = raw.lower().strip()
    if fmt in FORMATS:
        return fmt
    return DEFAULT_FORMAT if repli else None


_FORMAT_INVALIDE = {'format': 'Format invalide (csv, xlsx ou json).'}


@extend_schema(responses=inline_serializer('ExportObjetsListe', {
    'objects': serializers.ListField(child=serializers.DictField()),
    'formats': serializers.ListField(child=serializers.DictField()),
    'default_format': serializers.CharField()}))
@api_view(['GET'])
@permission_classes([IsAdminRole])
def export_objects_list(request):
    """Catalogue des objets exportables + formats disponibles (pour l'UI)."""
    return Response({
        'objects': available_objects(),
        'formats': [{'key': k, 'label': k.upper()} for k in FORMATS],
        'default_format': DEFAULT_FORMAT,
    })


#: Corps de ``POST export-object/`` : LE prédicat publié ET appliqué
#: (``corps_valide``) — un corps non objet, un ``object`` de type faux ou
#: inconnu répondent 400 (la lecture à la main levait AttributeError → 500).
_EXPORT_OBJET_REQUETE = inline_serializer('ExportObjetRequete', {
    'object': champ_choix(REGISTRY),
    # allow_blank : une valeur blanche est « inconnue » donc ramenée à csv
    # (ENF11 api-fuzz : le schéma n'exige plus un caractère visible).
    'format': ChaineStricte(
        required=False, allow_blank=True,
        help_text='csv, xlsx ou json ; valeur inconnue ⇒ csv.')})

#: Corps de ``POST sauvegarde/`` : chaque clé de ``objects`` doit être connue
#: (une clé inconnue ou vide était écartée en silence).
_SAUVEGARDE_REQUETE = inline_serializer('SauvegardeRequete', {
    'objects': serializers.ListField(
        child=champ_choix(REGISTRY), required=False),
    'format': champ_choix(FORMATS, required=False)})


@extend_schema(request=_EXPORT_OBJET_REQUETE, responses=_FICHIERS_EXPORT)
@api_view(['POST'])
@permission_classes([IsAdminRole])
@parser_classes(PARSEURS_JSON)
def export_object(request):
    """Exporte UN type d'objet de la société -> fichier téléchargeable."""
    company = _company_of(request.user)
    if company is None:
        return Response({'detail': 'Aucune société rattachée.'}, status=403)

    corps = corps_valide(request, _EXPORT_OBJET_REQUETE)
    key = corps['object']
    fmt = _clean_format(corps.get('format', _ABSENT), repli=True)
    if fmt is None:
        return Response(_FORMAT_INVALIDE, status=400)

    spec = REGISTRY[key]
    data = export_bytes(spec, company, fmt)
    resp = HttpResponse(data, content_type=FORMATS[fmt][1])
    resp['Content-Disposition'] = (
        f'attachment; filename="{filename_for(spec, fmt)}"'
    )
    return resp


@extend_schema(
    request=_SAUVEGARDE_REQUETE,
    responses={(200, 'application/zip'): OpenApiTypes.BINARY})
@api_view(['POST'])
@permission_classes([IsAdminRole])
@parser_classes(PARSEURS_JSON)
def sauvegarde(request):
    """Sauvegarde complète : bundle ZIP des objets choisis (un fichier/objet).

    ``objects`` (liste de clés) et ``format`` sont configurables ; par défaut
    tous les objets au format CSV.
    """
    company = _company_of(request.user)
    if company is None:
        return Response({'detail': 'Aucune société rattachée.'}, status=403)

    corps = corps_valide(request, _SAUVEGARDE_REQUETE)
    keys = _clean_objects(corps.get('objects'))
    fmt = _clean_format(corps.get('format', _ABSENT))
    if fmt is None:
        return Response(_FORMAT_INVALIDE, status=400)
    stamp = datetime.date.today().isoformat()
    specs = [REGISTRY[k] for k in keys]

    data = build_backup_zip(specs, company, fmt, stamp)
    resp = HttpResponse(data, content_type='application/zip')
    resp['Content-Disposition'] = (
        f'attachment; filename="{backup_filename(company, stamp)}"'
    )
    return resp
