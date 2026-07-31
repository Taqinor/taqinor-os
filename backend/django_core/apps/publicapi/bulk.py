"""NTAPI13/14/15/16/43 — jobs bulk (export/import) de l'API publique.

Machinerie PARTAGÉE par les endpoints qui manipulent un `BulkJob` :

  * `POST /api/public/exports/`            (NTAPI14) — crée + lance un export.
  * `POST /api/public/imports/`            (NTAPI15) — crée + lance un import.
  * `GET  /api/public/jobs/…`              (NTAPI16) — suivi (statut/%/liens).
  * `POST /api/public/jobs/<id>/relancer/` (NTAPI43) — reprise sur curseur.

Traitement HORS requête (Celery, `tasks.py`) mais chaque fonction `run_*` est
un pur appelable synchrone (testable sans broker — la tâche Celery n'est
qu'un mince wrapper qui l'invoque par `job_id`). Si le broker est injoignable,
on traite EN LIGNE plutôt que de laisser un job orphelin bloqué `en_file`
(dégradation propre, jamais un 500 côté appelant HTTP puisque le job est déjà
créé et renvoyé avant ce traitement).

Réutilise STRICTEMENT les points d'entrée déjà sanctionnés :
  * lecture — les MÊMES querysets/serializers que `public_views.py` (jamais
    une seconde définition qui pourrait diverger et exposer un prix d'achat) ;
  * écriture — `apps.crm.services` (jamais un import direct de `apps.crm.models`) ;
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
IMPORTABLE_ENTITIES = ('leads', 'activites')
IMPORT_MODES = ('create', 'upsert')
IMPORT_DEDUP_KEYS = ('email', 'telephone')
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


# ── NTAPI15 — Import ─────────────────────────────────────────────────────────

def _store_import_source(file_bytes, *, company_id, job_id, ext):
    from apps.records.storage import get_minio_client, ensure_uploads_bucket
    from django.conf import settings

    key = f'imports/{company_id or 0}/{job_id}.{ext}'
    client = get_minio_client()
    ensure_uploads_bucket()
    client.upload_fileobj(
        io.BytesIO(file_bytes), settings.MINIO_BUCKET_UPLOADS, key)
    return key


def _fetch_bytes(key):
    from apps.records.storage import fetch_attachment
    data, err = fetch_attachment(key)
    if err:
        raise BulkJobError(err)
    return data


def create_import_job(*, company, api_key, entite, mode='create',
                      dedup_key=None, file_bytes, filename=''):
    """Crée un `BulkJob` import `en_file` (fichier déposé en MinIO) et
    dispatche son traitement."""
    if entite not in IMPORTABLE_ENTITIES:
        raise BulkJobError(
            f"Entité inconnue : {entite!r} (attendu : "
            f"{', '.join(IMPORTABLE_ENTITIES)}).")
    mode = (mode or 'create').lower()
    if mode not in IMPORT_MODES:
        raise BulkJobError(
            f"Mode inconnu : {mode!r} (attendu : {', '.join(IMPORT_MODES)}).")
    if mode == 'upsert' and dedup_key not in IMPORT_DEDUP_KEYS:
        raise BulkJobError(
            "Clé de dédup requise en mode upsert (attendu : "
            f"{', '.join(IMPORT_DEDUP_KEYS)}).")
    if not file_bytes:
        raise BulkJobError('Fichier vide ou manquant (champ « file »).')

    ext = 'jsonl' if (filename or '').lower().endswith('.jsonl') else 'csv'
    job = BulkJob.objects.create(
        company=company, api_key=api_key, type=BulkJob.TYPE_IMPORT,
        entite=entite,
        params={'mode': mode, 'dedup_key': dedup_key, 'format': ext,
                'filename': (filename or '')[:255]})
    source_key = _store_import_source(
        file_bytes, company_id=job.company_id, job_id=job.id, ext=ext)
    job.params['source_file_key'] = source_key
    job.save(update_fields=['params'])
    _dispatch_import(job)
    return job


def _dispatch_import(job):
    from .tasks import process_bulk_import_job
    try:
        process_bulk_import_job.delay(job.id)
    except Exception:  # noqa: BLE001 — broker injoignable : jamais un job orphelin
        logger.exception(
            'BulkJob import %s : envoi Celery impossible, traitement inline',
            job.id)
        run_import_job(job.id)


def _parse_rows(raw_bytes, fmt):
    """Renvoie [(numéro_ligne, dict)] — une ligne illisible devient une ligne
    en erreur (`__parse_error__`) au lieu de faire échouer tout le fichier."""
    text = raw_bytes.decode('utf-8-sig', errors='replace')
    rows = []
    if fmt == 'jsonl':
        for i, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append((i, json.loads(line)))
            except (ValueError, TypeError) as exc:
                rows.append((i, {'__parse_error__': str(exc)}))
    else:
        reader = csv.DictReader(io.StringIO(text))
        for i, row in enumerate(reader, start=1):
            rows.append((i, dict(row)))
    return rows


def _process_lead_row(company, mode, dedup_key, row):
    from apps.crm import services as crm_services

    if mode == 'upsert' and dedup_key:
        value = (row.get(dedup_key) or '').strip()
        existing = None
        if value:
            if dedup_key == 'email':
                existing = crm_services.find_lead_by_email(company, value)
            elif dedup_key == 'telephone':
                existing = crm_services.find_lead_by_phone(company, value)
        if existing is not None:
            crm_services.update_lead_from_public_api(
                company=company, lead_id=existing.id, fields=row)
            return
    crm_services.create_lead_from_public_api(company=company, fields=row)


def _process_activite_row(company, row):
    from apps.crm.services import create_activity_from_public_api

    lead_id = row.get('lead_id')
    if not lead_id:
        raise BulkJobError("Champ « lead_id » requis.")
    create_activity_from_public_api(
        company=company, lead_id=lead_id, body=row.get('body'))


def run_import_job(job_id, *, batch_size=DEFAULT_BATCH_SIZE):
    """Traite un job d'import du début à la fin — IDEMPOTENT (reprend depuis
    `job.cursor`, NTAPI43). Une ligne en erreur n'arrête JAMAIS les
    suivantes ; toutes les erreurs sont journalisées dans
    `erreurs_file_key` (JSONL : ligne/erreur/données)."""
    try:
        job = BulkJob.objects.select_related('company').get(
            id=job_id, type=BulkJob.TYPE_IMPORT)
    except BulkJob.DoesNotExist:
        logger.warning('BulkJob import %s introuvable — abandon', job_id)
        return
    if job.statut == BulkJob.STATUT_TERMINE:
        return

    params = job.params or {}
    source_key = params.get('source_file_key')
    fmt = params.get('format', 'csv')
    mode = params.get('mode', 'create')
    dedup_key = params.get('dedup_key')

    try:
        raw = _fetch_bytes(source_key)
    except BulkJobError as exc:
        job.marquer_echec(str(exc))
        return

    rows = _parse_rows(raw, fmt)
    total = len(rows)
    start = job.cursor  # NTAPI43 — reprise : jamais retraiter une ligne déjà appliquée
    succes = job.succes
    erreurs_count = job.erreurs
    error_rows = []
    if job.erreurs_file_key:
        try:
            previous = _fetch_bytes(job.erreurs_file_key)
            error_rows = [
                json.loads(line) for line in previous.decode('utf-8').splitlines()
                if line.strip()
            ]
        except Exception:  # noqa: BLE001 — repli : repart d'un journal vide
            error_rows = []

    job.marquer_progression(total=total, cursor=start)

    for ligne, row in rows[start:]:
        if row.get('__parse_error__'):
            erreurs_count += 1
            error_rows.append({
                'ligne': ligne, 'erreur': row['__parse_error__'], 'donnees': {}})
        else:
            try:
                if job.entite == 'leads':
                    _process_lead_row(job.company, mode, dedup_key, row)
                else:
                    _process_activite_row(job.company, row)
                succes += 1
            except Exception as exc:  # noqa: BLE001 — une ligne en erreur n'arrête PAS les suivantes
                erreurs_count += 1
                error_rows.append(
                    {'ligne': ligne, 'erreur': str(exc), 'donnees': row})
        job.marquer_progression(
            traites=ligne, succes=succes, erreurs=erreurs_count, cursor=ligne)

    erreurs_file_key = ''
    if error_rows:
        blob = '\n'.join(
            json.dumps(r, ensure_ascii=False, default=str) for r in error_rows
        ).encode('utf-8')
        from apps.records.storage import store_export_result
        erreurs_file_key = store_export_result(
            blob, company_id=job.company_id, job_id=f'{job.id}-erreurs',
            ext='jsonl', content_type='application/x-ndjson')

    job.marquer_termine(erreurs_file_key=erreurs_file_key)


# ── NTAPI43 — Reprise sur curseur ────────────────────────────────────────────

def relancer_job(job):
    """Relance un `BulkJob` EN ÉCHEC (ou resté bloqué `en_cours`, ex. worker
    tué) depuis son `cursor` PERSISTANT — jamais de zéro, jamais de doublon
    (les lignes déjà appliquées avant `cursor` ne sont jamais rejouées).
    Refuse un job déjà `termine`/`en_file` (rien à reprendre)."""
    if job.statut not in (BulkJob.STATUT_ECHEC, BulkJob.STATUT_EN_COURS):
        raise BulkJobError(
            "Seul un job en échec (ou bloqué en cours) peut être relancé.")
    job.statut = BulkJob.STATUT_EN_FILE
    job.message_erreur = ''
    job.save(update_fields=['statut', 'message_erreur', 'updated_at'])
    if job.type == BulkJob.TYPE_EXPORT:
        _dispatch_export(job)
    else:
        _dispatch_import(job)
    return job
