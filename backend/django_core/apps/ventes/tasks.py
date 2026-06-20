"""
Celery tasks for async PDF generation.
Each task retries up to 3 times with exponential backoff.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='ventes.generate_devis_pdf',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def task_generate_devis_pdf(self, devis_id, pdf_options=None):
    """Generate the quote PDF for a Devis and store in MinIO. Retries on failure.

    Uses the premium quote engine when USE_PREMIUM_QUOTE_ENGINE is on (default),
    otherwise falls back to the legacy ventes WeasyPrint generator. Invoices are
    unaffected. pdf_options picks the simulator format (full premium 3 pages,
    one-page, monthly-chart / devis-final modifiers); the legacy fallback
    ignores it.
    """
    try:
        from django.conf import settings
        # ERR35 — idempotence sous acks_late + retry. La même tâche (mêmes
        # pdf_options) peut être ré-exécutée si le worker crashe APRÈS l'upload
        # MinIO mais AVANT l'ack ; on consigne la signature de contenu
        # (devis + pdf_options) la première fois et, si une ré-exécution
        # identique retrouve son PDF déjà présent dans MinIO, on le réutilise
        # tel quel — pas de re-rendu, pas de ré-écriture de fichier_pdf — ce qui
        # supprime la course sur l'écriture. Un appel avec d'AUTRES pdf_options
        # (autre format) ne correspond pas à la signature et re-rend normalement.
        # N'affecte que la voie premium.
        if getattr(settings, 'USE_PREMIUM_QUOTE_ENGINE', True):
            cached = _idempotent_cached_key(devis_id, pdf_options)
            if cached is not None:
                logger.info('task_generate_devis_pdf SKIP (déjà rendu): %s',
                            cached)
                return cached
            from .quote_engine import generate_premium_devis_pdf
            key = generate_premium_devis_pdf(devis_id, pdf_options)
            _remember_render(devis_id, pdf_options, key)
        else:
            from .utils.pdf import generate_devis_pdf
            key = generate_devis_pdf(devis_id)
        logger.info('task_generate_devis_pdf OK: %s', key)
        return key
    except Exception as exc:
        logger.error('task_generate_devis_pdf failed devis_id=%s: %s', devis_id, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


def _render_signature(devis_id, pdf_options):
    """Signature stable (devis + options de format) d'un rendu de PDF devis."""
    import hashlib
    import json
    payload = json.dumps(
        {'devis': devis_id, 'opts': pdf_options or {}},
        sort_keys=True, default=str)
    return 'devis-pdf:' + hashlib.sha256(payload.encode()).hexdigest()


def _idempotent_cached_key(devis_id, pdf_options):
    """Clé MinIO déjà rendue pour cette signature SI le PDF existe encore.

    Renvoie la clé réutilisable (skip du re-rendu) ou None (rendu requis).
    Best-effort : toute erreur de cache/MinIO retombe sur un rendu normal.
    """
    try:
        from django.core.cache import cache
        key = cache.get(_render_signature(devis_id, pdf_options))
        if key and _pdf_exists(key):
            return key
    except Exception:
        pass
    return None


def _remember_render(devis_id, pdf_options, key):
    """Mémorise la clé rendue pour cette signature (best-effort, 1 h)."""
    try:
        from django.core.cache import cache
        cache.set(_render_signature(devis_id, pdf_options), key, 3600)
    except Exception:
        pass


def _pdf_exists(key):
    """True si l'objet PDF existe déjà dans MinIO (best-effort, sans lever)."""
    try:
        from django.conf import settings
        from .utils.minio_client import get_minio_client
        get_minio_client().head_object(
            Bucket=settings.MINIO_BUCKET_PDF, Key=key)
        return True
    except Exception:
        return False


@shared_task(
    bind=True,
    name='ventes.generate_facture_pdf',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def task_generate_facture_pdf(self, facture_id):
    """Generate PDF for Facture and store in MinIO. Retries on failure."""
    try:
        from .utils.pdf import generate_facture_pdf
        key = generate_facture_pdf(facture_id)
        logger.info('task_generate_facture_pdf OK: %s', key)
        return key
    except Exception as exc:
        logger.error('task_generate_facture_pdf failed facture_id=%s: %s', facture_id, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
