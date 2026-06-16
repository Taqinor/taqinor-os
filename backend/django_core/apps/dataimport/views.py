"""T9 — endpoints d'import réutilisable (dry-run + commit). Multi-tenant :
la société vient toujours du serveur, jamais du corps."""
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from . import services


def _read(request):
    f = request.FILES.get('file')
    target = request.data.get('target')
    if f is None:
        return None, None, Response({'detail': 'Aucun fichier fourni.'}, status=400)
    if target not in services.TARGETS:
        return None, None, Response(
            {'detail': "Cible invalide (leads, clients ou products)."}, status=400)
    return f, target, None


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def dry_run(request):
    """Aperçu d'import (10 lignes + mapping colonne→champ) AVANT validation."""
    f, target, err = _read(request)
    if err:
        return err
    try:
        result = services.dry_run(f.read(), f.name, target)
    except Exception as exc:
        return Response({'detail': f'Lecture impossible : {exc}'}, status=400)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def commit(request):
    """Import effectif : création uniquement, doublons ignorés, origine marquée."""
    f, target, err = _read(request)
    if err:
        return err
    try:
        result = services.commit(
            f.read(), f.name, target, request.user.company, request.user)
    except Exception as exc:
        return Response({'detail': f'Import impossible : {exc}'}, status=400)
    return Response(result)
