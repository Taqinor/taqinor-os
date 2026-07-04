"""T9 — endpoints d'import réutilisable (dry-run + commit). Multi-tenant :
la société vient toujours du serveur, jamais du corps."""
import logging

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from authentication.permissions import (
    IsResponsableOrAdmin, HasPermissionAndRole,
)
from . import services

logger = logging.getLogger(__name__)

# QG4 — la CRÉATION de produits est restreinte partout (REST, import de
# données, OCR) aux rôles Directeur et Commercial responsable. Le commit
# d'import `products` porte donc la même garde que ProduitViewSet.create ;
# les autres cibles (leads, clients, fournisseurs, équipements…) gardent la
# règle historique (responsable/admin).
PRODUIT_CREATE_PERMISSION = HasPermissionAndRole(
    'stock_creer', 'Directeur', 'Commercial responsable')

# ERR53 — Bornes anti-DoS : un upload trop gros (en octets) ou un fichier de
# trop de lignes est rejeté AVANT toute lecture/parsing intégral en mémoire,
# avec un 400 clair plutôt qu'une erreur générique avalée.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 Mo
MAX_ROWS = 10000


def _read(request):
    f = request.FILES.get('file')
    target = request.data.get('target')
    if f is None:
        return None, None, Response({'detail': 'Aucun fichier fourni.'}, status=400)
    if target not in services.TARGETS:
        cibles = ', '.join(sorted(services.TARGETS))
        return None, None, Response(
            {'detail': f'Cible invalide (valeurs possibles : {cibles}).'},
            status=400)
    size = getattr(f, 'size', None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        return None, None, Response(
            {'detail': 'Fichier trop volumineux : '
                       f'{size} octets (max {MAX_UPLOAD_BYTES}).'},
            status=400)
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
    except ValueError as exc:
        # Erreur attendue (cible inconnue, plafond de lignes…) : message clair.
        return Response({'detail': str(exc)}, status=400)
    except Exception:
        # ERR53 — diagnostic : on journalise la cause réelle côté serveur sans
        # la divulguer au client, et on renvoie un 400 générique.
        logger.warning('Import dry-run échoué (target=%s)', target, exc_info=True)
        return Response(
            {'detail': 'Lecture du fichier impossible (format invalide ?).'},
            status=400)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def commit(request):
    """Import effectif : création uniquement, doublons ignorés, origine marquée."""
    f, target, err = _read(request)
    if err:
        return err
    # QG4 — l'import de PRODUITS crée des produits : même restriction que le
    # create REST (Directeur + Commercial responsable uniquement).
    if target == 'products' and not PRODUIT_CREATE_PERMISSION().has_permission(
            request, None):
        return Response(
            {'detail': 'La création de produits est réservée aux rôles '
                       'Directeur et Commercial responsable.'},
            status=403)
    try:
        result = services.commit(
            f.read(), f.name, target, request.user.company, request.user)
    except ValueError as exc:
        # Erreur attendue (cible inconnue, plafond de lignes…) : message clair.
        return Response({'detail': str(exc)}, status=400)
    except Exception:
        # ERR53 — diagnostic : on journalise la cause réelle côté serveur sans
        # la divulguer au client, et on renvoie un 400 générique. Le commit est
        # atomique (ERR51) : rien n'est créé en cas d'échec.
        logger.warning('Import commit échoué (target=%s)', target, exc_info=True)
        return Response(
            {'detail': 'Import impossible (vérifiez le fichier).'},
            status=400)
    return Response(result)
