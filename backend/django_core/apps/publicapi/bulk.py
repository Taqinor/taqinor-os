"""NTAPI13/14 — jobs bulk EXPORT de l'API publique.

Machinerie du `BulkJob` export (voir `models.BulkJob`, NTAPI13 — schéma
minimal introduit ICI, requis par NTAPI14) :

  * `POST /api/public/exports/` (NTAPI14) — crée + lance un export.

L'import (NTAPI15), le suivi de job (NTAPI16) et la reprise sur curseur
(NTAPI43) viendront s'ADDITIONNER à ce module dans une tâche suivante — sans
rien réécrire ici.

Traitement HORS requête (Celery, `tasks.py`) mais `run_export_job` est un pur
appelable synchrone (testable sans broker — la tâche Celery n'est qu'un
mince wrapper qui l'invoque par `job_id`). Si le broker est injoignable, on
traite EN LIGNE plutôt que de laisser un job orphelin bloqué `en_file`
(dégradation propre, jamais un 500 côté appelant HTTP puisque le job est déjà
créé et renvoyé avant ce traitement).

Réutilise STRICTEMENT les points d'entrée déjà sanctionnés :
  * lecture — les MÊMES querysets/serializers que `public_views.py` (jamais
    une seconde définition qui pourrait diverger et exposer un prix d'achat) ;
  * stockage — `apps.records.storage` (MinIO, isolation par société existante).
"""
import csv
import io
import json
import logging

from .models import BulkJob

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 500

EXPORTABLE_ENTITIES = ('leads', 'devis', 'factures', 'chantiers', 'produits')
EXPORT_FORMATS = ('csv', 'jsonl')


class BulkJobError(ValueError):
    """Entrée utilisateur invalide (traduite en 400 par la vue) — jamais un 500."""


def _export_registry():
    # Import paresseux : `public_views` est déjà chargé par `public_urls` au
    # démarrage — on évite juste un import de niveau module ici pour ne rien
    # figer avant que les apps soient prêtes.
    from .public_views import (
        PublicLeadViewSet, PublicDevisViewSet, PublicFactureViewSet,
        PublicChantierViewSet, PublicProduitViewSet,
    )
    return {
        'leads': PublicLeadViewSet,
        'devis': PublicDevisViewSet,
        'factures': PublicFactureViewSet,
        'chantiers': PublicChantierViewSet,
        'produits': PublicProduitViewSet,
    }


# ── NTAPI14 — Export ─────────────────────────────────────────────────────────

def create_export_job(*, company, api_key, entite, fmt='csv', filtres=None):
    """Crée un `BulkJob` export `en_file` et dispatche son traitement."""
    if entite not in EXPORTABLE_ENTITIES:
        raise BulkJobError(
            f"Entité inconnue : {entite!r} (attendu : "
            f"{', '.join(EXPORTABLE_ENTITIES)}).")
    fmt = (fmt or 'csv').lower()
    if fmt not in EXPORT_FORMATS:
        raise BulkJobError(
            f"Format inconnu : {fmt!r} (attendu : {', '.join(EXPORT_FORMATS)}).")
    if filtres is not None and not isinstance(filtres, dict):
        raise BulkJobError('« filtres » doit être un objet.')
    job = BulkJob.objects.create(
        company=company, api_key=api_key, type=BulkJob.TYPE_EXPORT,
        entite=entite, params={'format': fmt, 'filtres': filtres or {}})
    _dispatch_export(job)
    return job


def _dispatch_export(job):
    from .tasks import process_bulk_export_job
    try:
        process_bulk_export_job.delay(job.id)
    except Exception:  # noqa: BLE001 — broker injoignable : jamais un job orphelin
        logger.exception(
            'BulkJob export %s : envoi Celery impossible, traitement inline',
            job.id)
        run_export_job(job.id)


def _serialize_row(serializer_class, instance):
    data = serializer_class(instance).data
    # CSV/JSONL exigent un enregistrement PLAT (jamais de sous-liste comme
    # `lignes` sur devis/factures) — un champ non-scalaire est déposé en JSON
    # dans sa cellule plutôt que de casser la forme tabulaire.
    flat = {}
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            flat[key] = json.dumps(value, ensure_ascii=False, default=str)
        else:
            flat[key] = value
    return flat


def run_export_job(job_id, *, batch_size=DEFAULT_BATCH_SIZE):
    """Traite un job d'export du début à la fin — IDEMPOTENT (peut être
    ré-invoqué depuis `job.cursor`, NTAPI43, sans doublon)."""
    try:
        job = BulkJob.objects.select_related('company').get(
            id=job_id, type=BulkJob.TYPE_EXPORT)
    except BulkJob.DoesNotExist:
        logger.warning('BulkJob export %s introuvable — abandon', job_id)
        return
    if job.statut == BulkJob.STATUT_TERMINE:
        return  # déjà terminé : un rejeu (ex. tâche dupliquée) est un no-op

    viewset_cls = _export_registry().get(job.entite)
    if viewset_cls is None:
        job.marquer_echec(f"Entité inconnue : {job.entite!r}.")
        return

    params = job.params or {}
    fmt = params.get('format', 'csv')
    filtres = params.get('filtres') or {}
    serializer_class = viewset_cls.serializer_class
    queryset = viewset_cls.queryset.filter(company_id=job.company_id)
    whitelist = getattr(viewset_cls, 'filter_whitelist', ())
    for key, value in filtres.items():
        if key not in whitelist:
            continue  # même liste blanche que la lecture synchrone (FG104)
        queryset = queryset.filter(**{key: value})

    total = queryset.count()
    start = job.cursor  # NTAPI43 — reprise : ne recommence jamais de zéro
    job.marquer_progression(total=total, cursor=start)

    buf = io.StringIO()
    writer = None
    written = job.succes

    try:
        offset = start
        while offset < total:
            chunk = list(queryset[offset:offset + batch_size])
            if not chunk:
                break
            for instance in chunk:
                row = _serialize_row(serializer_class, instance)
                if fmt == 'jsonl':
                    buf.write(json.dumps(row, ensure_ascii=False, default=str))
                    buf.write('\n')
                else:
                    if writer is None:
                        writer = csv.DictWriter(buf, fieldnames=list(row.keys()))
                        writer.writeheader()
                    writer.writerow(row)
                written += 1
            offset += len(chunk)
            job.marquer_progression(traites=offset, succes=written, cursor=offset)
    except Exception as exc:  # noqa: BLE001
        logger.exception('BulkJob export %s : échec au curseur %s',
                         job.id, job.cursor)
        job.marquer_echec(str(exc))
        return

    from apps.records.storage import store_export_result
    data = buf.getvalue().encode('utf-8')
    ext = 'jsonl' if fmt == 'jsonl' else 'csv'
    content_type = 'application/x-ndjson' if fmt == 'jsonl' else 'text/csv'
    key = store_export_result(
        data, company_id=job.company_id, job_id=job.id, ext=ext,
        content_type=content_type)
    job.marquer_progression(traites=total, succes=written, cursor=total)
    job.marquer_termine(resultat_file_key=key)
