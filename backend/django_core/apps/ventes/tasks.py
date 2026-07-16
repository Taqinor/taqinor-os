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


def _content_version(devis_id):
    """QG2 — Empreinte du CONTENU d'un devis (lignes + totaux + méta).

    Le cache d'idempotence du rendu était keyé sur (devis_id, pdf_options)
    uniquement : après une édition « Éditer », les MÊMES options renvoyaient
    l'ANCIEN PDF depuis MinIO (contenu périmé). On intègre donc une empreinte
    du contenu à la signature de rendu : au moindre changement de lignes, de
    remise/TVA globale, de version ou de statut, l'empreinte change → le cache
    « rate » → le PDF est re-rendu ; à contenu identique, l'empreinte est
    stable → le cache reste bénéfique (pas de re-rendu inutile).

    Best-effort : toute erreur renvoie une empreinte vide, ce qui revient au
    comportement historique (signature sur options seules)."""
    import hashlib
    import json
    try:
        from .models import Devis, LigneDevis
        devis = (Devis.objects
                 .filter(pk=devis_id)
                 .values('remise_globale', 'taux_tva', 'version', 'statut',
                         'mode_installation', 'etude_params', 'prix_cible_kwc')
                 .first())
        if devis is None:
            return ''
        lignes = list(
            LigneDevis.objects.filter(devis_id=devis_id)
            .order_by('id')
            .values('id', 'produit_id', 'designation', 'quantite',
                    'prix_unitaire', 'remise', 'taux_tva'))
        payload = json.dumps(
            {'devis': devis, 'lignes': lignes},
            sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()
    except Exception:  # noqa: BLE001 — best-effort → repli historique
        return ''


def _render_signature(devis_id, pdf_options):
    """Signature stable (devis + CONTENU + options de format) d'un rendu.

    QG2 — inclut désormais l'empreinte du contenu (`_content_version`) pour
    qu'une édition invalide le cache de rendu tout en gardant le bénéfice du
    cache à contenu inchangé."""
    import hashlib
    import json
    payload = json.dumps(
        {'devis': devis_id, 'content': _content_version(devis_id),
         'opts': pdf_options or {}},
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


# ── SCA41 — export xlsx asynchrone (pilote de NTPLT29/30) ───────────────────
# Cache : durée de vie d'un job d'export (état + clé MinIO + société), sous une
# clé opaque (id de tâche). Le endpoint de statut vérifie la société stockée
# AVANT de renvoyer quoi que ce soit (jamais d'accès inter-tenant).
EXPORT_JOB_CACHE_PREFIX = 'ventes:export_job:'
EXPORT_JOB_CACHE_TTL = 24 * 3600  # 24 h


def export_job_cache_key(token):
    return f'{EXPORT_JOB_CACHE_PREFIX}{token}'


@shared_task(
    bind=True,
    name='ventes.build_async_export',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def task_build_async_export(self, company_id, layout, debut_iso, fin_iso, token):
    """SCA41 — construit un export xlsx volumineux HORS requête et le stocke
    dans MinIO sous une clé préfixée société (motif ERR75). Met à jour l'état
    du job en cache (``pending`` → ``ready``/``error``). Réutilise le builder
    synchrone → octets STRICTEMENT identiques à l'export in-request.

    Le futur ``BackgroundJob`` générique (NTPLT29/30) remplacera cette tâche en
    conservant la même signature de sortie (clé MinIO + nom de fichier)."""
    from datetime import date
    from django.core.cache import cache
    from django.conf import settings
    from .exports import build_export_xlsx_bytes, export_object_key
    from .utils.minio_client import get_minio_client

    ckey = export_job_cache_key(token)
    try:
        debut = date.fromisoformat(debut_iso)
        fin = date.fromisoformat(fin_iso)
        content, filename = build_export_xlsx_bytes(
            company_id, layout, debut, fin)
        key = export_object_key(company_id, layout, debut, fin, token)
        client = get_minio_client()
        client.put_object(
            Bucket=settings.MINIO_BUCKET_PDF,
            Key=key,
            Body=content,
            ContentType=('application/vnd.openxmlformats-officedocument'
                         '.spreadsheetml.sheet'),
        )
        job = cache.get(ckey) or {}
        job.update({'company_id': company_id, 'layout': layout,
                    'status': 'ready', 'key': key, 'filename': filename})
        cache.set(ckey, job, EXPORT_JOB_CACHE_TTL)
        logger.info('task_build_async_export OK: %s', key)
        return key
    except Exception as exc:  # noqa: BLE001
        job = cache.get(ckey) or {}
        job.update({'company_id': company_id, 'layout': layout,
                    'status': 'error', 'error': str(exc)})
        cache.set(ckey, job, EXPORT_JOB_CACHE_TTL)
        logger.error('task_build_async_export failed company=%s layout=%s: %s',
                     company_id, layout, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
