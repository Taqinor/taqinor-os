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
        if getattr(settings, 'USE_PREMIUM_QUOTE_ENGINE', True):
            from .quote_engine import generate_premium_devis_pdf
            key = generate_premium_devis_pdf(devis_id, pdf_options)
        else:
            from .utils.pdf import generate_devis_pdf
            key = generate_devis_pdf(devis_id)
        logger.info('task_generate_devis_pdf OK: %s', key)
        return key
    except Exception as exc:
        logger.error('task_generate_devis_pdf failed devis_id=%s: %s', devis_id, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


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
