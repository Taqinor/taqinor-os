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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminRole

from .exporters import (
    DEFAULT_FORMAT, FORMATS, backup_filename, build_backup_zip,
    export_bytes, filename_for,
)
from .export_registry import (
    DEFAULT_OBJECTS, REGISTRY, available_objects,
)


def _company_of(user):
    """Société de l'utilisateur, ou None si non rattaché (superuser nu)."""
    return user.company if user.company_id else None


def _clean_objects(raw):
    """Garde uniquement les clés connues, dans l'ordre du registre.

    Liste vide / absente -> défaut (tous les objets).
    """
    if not raw:
        return list(DEFAULT_OBJECTS)
    if isinstance(raw, str):
        raw = [s.strip() for s in raw.split(',') if s.strip()]
    requested = {k for k in raw if k in REGISTRY}
    keys = [k for k in REGISTRY if k in requested]
    return keys or list(DEFAULT_OBJECTS)


def _clean_format(raw):
    fmt = (raw or DEFAULT_FORMAT)
    if isinstance(fmt, str):
        fmt = fmt.lower().strip()
    return fmt if fmt in FORMATS else DEFAULT_FORMAT


@api_view(['GET'])
@permission_classes([IsAdminRole])
def export_objects_list(request):
    """Catalogue des objets exportables + formats disponibles (pour l'UI)."""
    return Response({
        'objects': available_objects(),
        'formats': [{'key': k, 'label': k.upper()} for k in FORMATS],
        'default_format': DEFAULT_FORMAT,
    })


@api_view(['POST'])
@permission_classes([IsAdminRole])
def export_object(request):
    """Exporte UN type d'objet de la société -> fichier téléchargeable."""
    company = _company_of(request.user)
    if company is None:
        return Response({'detail': 'Aucune société rattachée.'}, status=403)

    key = (request.data.get('object') or '').strip()
    if key not in REGISTRY:
        return Response({'detail': 'Objet inconnu.'}, status=400)
    fmt = _clean_format(request.data.get('format'))

    spec = REGISTRY[key]
    data = export_bytes(spec, company, fmt)
    resp = HttpResponse(data, content_type=FORMATS[fmt][1])
    resp['Content-Disposition'] = (
        f'attachment; filename="{filename_for(spec, fmt)}"'
    )
    return resp


@api_view(['POST'])
@permission_classes([IsAdminRole])
def sauvegarde(request):
    """Sauvegarde complète : bundle ZIP des objets choisis (un fichier/objet).

    ``objects`` (liste de clés) et ``format`` sont configurables ; par défaut
    tous les objets au format CSV.
    """
    company = _company_of(request.user)
    if company is None:
        return Response({'detail': 'Aucune société rattachée.'}, status=403)

    keys = _clean_objects(request.data.get('objects'))
    fmt = _clean_format(request.data.get('format'))
    stamp = datetime.date.today().isoformat()
    specs = [REGISTRY[k] for k in keys]

    data = build_backup_zip(specs, company, fmt, stamp)
    resp = HttpResponse(data, content_type='application/zip')
    resp['Content-Disposition'] = (
        f'attachment; filename="{backup_filename(company, stamp)}"'
    )
    return resp
