"""FG42 — Vues d'import de relevé bancaire (dry-run + commit).

Réutilise le même pattern que dataimport : deux endpoints POST (aperçu avant
validation puis import effectif). Scopé société, jamais d'écriture en dry-run.
"""
import logging

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 Mo


def _read_file(request):
    f = request.FILES.get('file')
    if f is None:
        return None, None, Response({'detail': 'Aucun fichier fourni.'}, status=400)
    size = getattr(f, 'size', None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        return None, None, Response(
            {'detail': f'Fichier trop volumineux (max 5 Mo, reçu {size} octets).'},
            status=400)
    return f.read(), f.name, None


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def releve_dry_run(request):
    """FG42 — Aperçu du relevé bancaire (dry-run, aucune écriture).

    POST /ventes/paiements/import-releve/dry-run/
    Corps : fichier XLSX ou CSV (champ ``file``).

    Renvoie le mapping colonnes, un aperçu des 10 premières lignes avec le
    statut de chaque ligne (a_importer, non_trouve, deja_regle, surpaiement,
    montant_invalide, ambigu, client_non_identifie), la FILE DE REVUE
    (``revue``) et — AUD121 — le ``token`` à repasser au commit.
    """
    from ..paiement_import import dry_run
    file_bytes, filename, err = _read_file(request)
    if err:
        return err
    company = request.user.company
    try:
        result = dry_run(file_bytes, filename, company, user=request.user)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    except Exception:
        logger.warning('Relevé dry-run échoué', exc_info=True)
        return Response(
            {'detail': 'Lecture du fichier impossible (format invalide ?).'},
            status=400)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def releve_commit(request):
    """FG42 — Import effectif du relevé bancaire.

    POST /ventes/paiements/import-releve/commit/
    Corps : ``{token, lignes?}`` — le ``token`` rendu par le dry-run et,
    optionnellement, les numéros de ligne que l'opérateur a validés.

    AUD121 — le commit ne reçoit PLUS de fichier : il rejoue les décisions
    du dry-run correspondant. Sans jeton → 400 ; jeton déjà consommé → 400 ;
    contenu de fichier déjà importé pour cette société → 400 (c'est la
    déduplication du double-import). Réutilise la garde sur-paiement.
    """
    from ..paiement_import import commit
    company = request.user.company
    token = request.data.get('token')
    lignes = request.data.get('lignes')
    if lignes is not None and not isinstance(lignes, (list, tuple)):
        return Response(
            {'detail': 'lignes doit être une liste de numéros de ligne.'},
            status=400)
    try:
        result = commit(company, request.user, token, lignes=lignes)
    except (ValueError, TypeError) as exc:
        return Response({'detail': str(exc)}, status=400)
    except Exception:
        logger.warning('Relevé commit échoué', exc_info=True)
        return Response(
            {'detail': 'Import impossible (erreur inattendue).'},
            status=500)
    return Response(result, status=201 if result['created'] > 0 else 200)
