"""NTMIG35 — stockage OBJET des fichiers source de migration (MinIO).

Pourquoi pas un ``FileField`` : ARC26 interdit toute nouvelle pièce jointe hors
stockage objet — un fichier posé sur le disque d'un conteneur disparaît au
redéploiement et échappe à toute purge. Pourquoi pas ``records.Attachment`` non
plus : son pipeline n'accepte que PDF/images/audio (allowlist de sécurité
qu'on ne desserre pas pour faire passer un CSV). On réutilise donc le MÊME
client MinIO que ``records.storage`` (``apps.ventes.utils.minio_client``), avec
des clés préfixées par société (isolation SCA42), et on ne garde en base que la
CLÉ de l'objet.

Toutes les fonctions sont tolérantes aux pannes du stockage : un fichier source
est un CONFORT (rejouer/reprendre/tester à blanc), jamais la source de vérité —
son indisponibilité ne doit pas casser un import ni une purge.
"""
import io
import logging
import os
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

#: Préfixe des clés d'objet (bucket ``erp-uploads``).
PREFIXE = 'migration/sources'


def _client():
    from apps.ventes.utils.minio_client import (
        ensure_uploads_bucket, get_minio_client)

    client = get_minio_client()
    ensure_uploads_bucket()
    return client


def cle_pour(company_id, lot_id, filename):
    """Clé d'objet unique, préfixée par société (jamais devinable/écrasable)."""
    ext = os.path.splitext(filename or '')[1][:10] or '.csv'
    return f'{PREFIXE}/{company_id}/lot-{lot_id}-{uuid.uuid4().hex}{ext}'


def enregistrer(company_id, lot_id, octets, filename):
    """Téléverse le fichier source et renvoie sa clé (``''`` si le stockage
    est indisponible — l'import continue, seule la reprise sera impossible)."""
    cle = cle_pour(company_id, lot_id, filename)
    try:
        _client().upload_fileobj(
            io.BytesIO(octets), settings.MINIO_BUCKET_UPLOADS, cle,
            ExtraArgs={'ContentType': 'application/octet-stream'})
    except Exception:
        logger.warning(
            'NTMIG35 — fichier source non stocké (stockage objet '
            'indisponible) pour le lot %s.', lot_id, exc_info=True)
        return ''
    return cle


def lire(cle):
    """Octets de l'objet, ou ``None`` (clé vide, objet purgé, stockage HS)."""
    if not cle:
        return None
    try:
        obj = _client().get_object(
            Bucket=settings.MINIO_BUCKET_UPLOADS, Key=cle)
        return obj['Body'].read()
    except Exception:
        return None


def supprimer(cle):
    """Supprime l'objet — best-effort, jamais bloquant."""
    if not cle:
        return
    try:
        _client().delete_object(
            Bucket=settings.MINIO_BUCKET_UPLOADS, Key=cle)
    except Exception:
        logger.warning(
            'NTMIG35 — suppression du fichier source %s impossible.', cle,
            exc_info=True)
