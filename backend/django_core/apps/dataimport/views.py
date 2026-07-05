"""T9 — endpoints d'import réutilisable (dry-run + commit). Multi-tenant :
la société vient toujours du serveur, jamais du corps."""
import csv
import io
import logging

from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from authentication.permissions import (
    IsResponsableOrAdmin, HasPermissionAndRole,
)
from . import services
from .models import ImportJob

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
    """Aperçu d'import (10 lignes + mapping colonne→champ) AVANT validation.

    XPLT2 — ``mapping`` (nom d'un ``ImportMapping`` sauvegardé) réapplique un
    mapping colonne→champ mémorisé au lieu du mapping automatique par en-tête.
    """
    f, target, err = _read(request)
    if err:
        return err
    mapping_name = request.data.get('mapping') or None
    try:
        result = services.dry_run(
            f.read(), f.name, target, company=request.user.company,
            mapping_name=mapping_name)
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
    # XPLT1 — mode d'import optionnel (creer=défaut, maj, upsert), jamais lu
    # ailleurs que le body du formulaire (la société, elle, reste forcée
    # côté serveur via request.user.company).
    mode = (request.data.get('mode') or 'creer').strip().lower()
    external_system = request.data.get('external_system') or None
    # XPLT2 — mapping sauvegardé optionnel + choix commit partiel (défaut,
    # comportement historique) vs rollback atomique total si une ligne échoue.
    mapping_name = request.data.get('mapping') or None
    rollback_on_error = str(
        request.data.get('rollback_on_error') or '').strip().lower() in (
        '1', 'true', 'on', 'oui')
    try:
        result = services.commit(
            f.read(), f.name, target, request.user.company, request.user,
            mode=mode, external_system=external_system,
            mapping_name=mapping_name, rollback_on_error=rollback_on_error)
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


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def save_mapping(request):
    """XPLT2 — sauvegarde (ou remplace) un mapping colonne→champ nommé pour une
    cible, réapplicable au prochain dry-run/commit via ``mapping=<nom>``."""
    target = request.data.get('target')
    nom = (request.data.get('nom') or '').strip()
    mapping = request.data.get('mapping')
    if target not in services.TARGETS:
        cibles = ', '.join(sorted(services.TARGETS))
        return Response(
            {'detail': f'Cible invalide (valeurs possibles : {cibles}).'},
            status=400)
    if not nom:
        return Response({'detail': 'Nom de mapping requis.'}, status=400)
    if not isinstance(mapping, dict) or not mapping:
        return Response(
            {'detail': 'Mapping invalide (dict colonne→champ attendu).'},
            status=400)
    obj = services.save_mapping(request.user.company, target, nom, mapping)
    return Response({
        'id': obj.pk, 'target': obj.entity, 'nom': obj.nom, 'mapping': obj.mapping,
    })


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def job_erreurs_csv(request, job_id):
    """XPLT2 — CSV des seules lignes en échec d'un ``ImportJob``, directement
    ré-importables (mêmes en-têtes que le fichier d'origine + ``_motif``).
    Isolation tenant stricte : un job d'une autre société → 404."""
    job = ImportJob.objects.filter(
        pk=job_id, company=request.user.company).first()
    if job is None:
        return Response({'detail': 'Import introuvable.'}, status=404)
    fieldnames, rows = services.erreurs_csv_rows(job)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames or ['_motif'])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    resp = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="import_{job.pk}_erreurs.csv"'
    return resp
