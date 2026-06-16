from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

from . import service
from .specs import SPECS

MAX_FILE_BYTES = 8 * 1024 * 1024  # 8 Mo


def _read_upload(request):
    """Retourne (target, filename, content) ou lève une 400 via ValueError."""
    target = request.data.get('target')
    if target not in SPECS:
        raise ValueError('Type d\'import inconnu.')
    upload = request.FILES.get('file')
    if upload is None:
        raise ValueError('Aucun fichier fourni.')
    if upload.size and upload.size > MAX_FILE_BYTES:
        raise ValueError('Fichier trop volumineux (max 8 Mo).')
    content = upload.read()
    return target, upload.name, content


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def import_specs(request):
    """Liste les cibles d'import disponibles + leurs champs (pour l'UI)."""
    out = []
    for target, spec in SPECS.items():
        out.append({
            'target': target,
            'label': spec.label,
            'fields': [
                {'field': f.key, 'label': f.label, 'required': f.required}
                for f in spec.fields
            ],
        })
    return Response(out)


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def import_preview(request):
    """Aperçu dry-run (10 lignes) — ne persiste rien."""
    try:
        target, filename, content = _read_upload(request)
    except ValueError as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        data = service.build_preview(
            target, filename, content, request.user.company)
    except service.ImportError_ as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(data)


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def import_confirm(request):
    """Import complet (création seule, doublons ignorés, fiches origin-taggées)."""
    try:
        target, filename, content = _read_upload(request)
    except ValueError as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        data = service.run_import(
            target, filename, content, request.user.company, request.user)
    except service.ImportError_ as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(data, status=status.HTTP_201_CREATED)
