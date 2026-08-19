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


def _content_version(devis_id, pdf_options=None):
    """QG2 — Empreinte du CONTENU d'un devis (lignes + totaux + méta + calepinage).

    Le cache d'idempotence du rendu était keyé sur (devis_id, pdf_options)
    uniquement : après une édition « Éditer », les MÊMES options renvoyaient
    l'ANCIEN PDF depuis MinIO (contenu périmé). On intègre donc une empreinte
    du contenu à la signature de rendu : au moindre changement de lignes, de
    remise/TVA globale, de version ou de statut, l'empreinte change → le cache
    « rate » → le PDF est re-rendu ; à contenu identique, l'empreinte est
    stable → le cache reste bénéfique (pas de re-rendu inutile).

    PVFRESH (résidu, fondateur 19/08/2026) — cette empreinte lisait les
    champs du devis à la main (``.values(...)``) et OUBLIAIT
    ``roof_layout`` : un calepinage rejoué SANS toucher une ligne ne
    changeait donc pas l'empreinte Celery, alors qu'il change bien le PDF
    rendu (PVUNI : le kWc/production servis suivent le calepinage en repli, et
    ``layout_stale`` dépend de son compte de panneaux). Plutôt qu'ajouter
    ``roof_layout`` à la main ici — une DEUXIÈME dérivation qui pourrait
    encore diverger de celle utilisée pour SERVIR le PDF — on réutilise
    l'EXACTE empreinte PVFRESH (``quote_engine.empreinte_donnees_pdf`` sur
    ``build_quote_data``, celle-là même persistée dans
    ``Devis.pdf_render_meta`` par ``cle_pdf_a_jour``). Tâche Celery et vues
    jugent donc désormais la fraîcheur d'un devis avec la MÊME fonction,
    jamais une seconde implémentation.

    Best-effort : toute erreur renvoie une empreinte vide, ce qui revient au
    comportement historique (signature sur options seules)."""
    try:
        from .models import Devis
        from .quote_engine import build_quote_data, empreinte_donnees_pdf
        devis = Devis.objects.filter(pk=devis_id).first()
        if devis is None:
            return ''
        return empreinte_donnees_pdf(build_quote_data(devis, pdf_options)) or ''
    except Exception:  # noqa: BLE001 — best-effort → repli historique
        return ''


def _render_signature(devis_id, pdf_options):
    """Signature stable (devis + CONTENU + options de format) d'un rendu.

    QG2 — inclut l'empreinte du contenu (`_content_version`) pour qu'une
    édition (lignes, méta, OU calepinage — PVFRESH) invalide le cache de
    rendu tout en gardant le bénéfice du cache à contenu inchangé."""
    import hashlib
    import json
    payload = json.dumps(
        {'devis': devis_id,
         'content': _content_version(devis_id, pdf_options),
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


# ── PV74 — étude bankable ASYNCHRONE (simulation d'un devis) ────────────────
#
# ``run_bankable_study`` interroge PVGIS (productible + TMY) par pan de toiture :
# sur un toit à trois pans, c'est trois allers-retours réseau dans la requête du
# commercial — un slot gunicorn bloqué pendant des secondes, et un timeout au
# premier hoquet du réseau. La simulation part donc en Celery, EXACTEMENT sur le
# motif d'export asynchrone déjà en service dans cette app (SCA41,
# ``journal_view._maybe_async_export``) : un jeton opaque, l'état en cache scopé
# SOCIÉTÉ, et un endpoint de statut qui vérifie cette société avant de répondre.
#
# Ce que la tâche N'ÉCRIT PAS : le statut du devis, ses lignes, ses prix
# (règle #4). Elle ne pose QUE ``etude_params['simulation']``, chirurgicalement,
# via ``save(update_fields=['etude_params'])`` — le statut ne peut pas partir de
# là, même par accident.
SIMULATION_JOB_CACHE_PREFIX = 'ventes:simulation_job:'
SIMULATION_JOB_CACHE_TTL = 24 * 3600  # 24 h


def simulation_job_cache_key(token):
    return f'{SIMULATION_JOB_CACHE_PREFIX}{token}'


def zones_etude_du_devis(devis):
    """PV74 — les ZONES d'étude d'un devis : un pan de calepinage = une zone.

    La géométrie vient de ``roof_layout['_pans_geometry']`` (QJ21) — la seule
    source qui connaisse l'orientation RÉELLE de chaque pan ; le point GPS vient
    du LEAD (``gps_lat``/``gps_lng``), à défaut du repère posé dans l'outil 3D
    (``roof_layout['pin']``). L'azimut est déjà dans la convention PVGIS
    (0 = Sud) des deux côtés : aucune conversion ici, donc aucune occasion de
    retourner un toit.

    Rend ``[]`` quand le devis n'a aucun pan exploitable — l'appelant refuse
    alors la simulation plutôt que de lancer une étude vide. Ne lève jamais :
    un pan illisible est ignoré, pas fatal.
    """
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return []

    lat = lon = None
    lead = getattr(devis, 'lead', None)
    if lead is not None:
        lat = getattr(lead, 'gps_lat', None)
        lon = getattr(lead, 'gps_lng', None)
    if lat is None or lon is None:
        pin = layout.get('pin')
        if isinstance(pin, dict):
            lat = pin.get('lat') if lat is None else lat
            lon = pin.get('lng') if lon is None else lon

    def _f(valeur):
        try:
            return float(valeur)
        except (TypeError, ValueError):
            return None

    zones = []
    for index, pan in enumerate(layout.get('_pans_geometry') or [], start=1):
        if not isinstance(pan, dict):
            continue
        kwc = _f(pan.get('kwc'))
        if not kwc:
            continue
        zones.append({
            'label': str(pan.get('label') or 'Pan %d' % index),
            'lat': _f(lat),
            'lon': _f(lon),
            'tilt': _f(pan.get('inclinaison_deg')),
            'azimuth': _f(pan.get('azimut_deg')),
            'kwc': kwc,
        })
    return zones


def ranger_simulation(devis_id, simulation):
    """PV74 — range la simulation dans ``etude_params['simulation']``, et RIEN
    d'autre.

    Mise à jour CHIRURGICALE : les autres clés d'étude (autoconsommation,
    payback, pompe, toiture…) sont relues et réécrites telles quelles, et
    ``update_fields`` se limite à ``etude_params`` — le STATUT ne peut donc pas
    bouger depuis ce chemin (règle #4). Rend le devis rafraîchi, ou ``None``
    s'il a disparu entre-temps.
    """
    from .models import Devis

    devis = Devis.objects.filter(pk=devis_id).first()
    if devis is None:
        return None
    etude = dict(devis.etude_params or {})
    etude['simulation'] = simulation
    devis.etude_params = etude
    devis.save(update_fields=['etude_params'])
    return devis


@shared_task(
    bind=True,
    name='ventes.simulate_bankable_study',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def task_simulate_bankable_study(self, devis_id, company_id, token,
                                 force_refresh=False):
    """PV74 — exécute l'étude bankable d'un devis HORS requête et la range.

    Met à jour l'état du job en cache (``pending`` → ``ready``/``error``),
    scopé société comme l'export asynchrone (SCA41). Réutilise
    ``etude.run_bankable_study`` tel quel : le contenu de l'étude est
    STRICTEMENT celui du calcul synchrone (aucune seconde source de vérité).

    ``force_refresh`` traverse jusqu'aux fetchers PVGIS (PV73) : sans lui, deux
    simulations du même toit ne coûtent qu'un seul aller-retour réseau.
    """
    from django.core.cache import cache

    from .etude import run_bankable_study
    from .models import Devis

    ckey = simulation_job_cache_key(token)
    try:
        devis = Devis.objects.filter(pk=devis_id,
                                     company_id=company_id).first()
        if devis is None:
            # Devis supprimé (ou d'une autre société) : ÉCHEC net, jamais un
            # retry — réessayer ne le fera pas réapparaître.
            cache.set(ckey, {'company_id': company_id, 'devis_id': devis_id,
                             'status': 'error', 'error': 'Devis introuvable.'},
                      SIMULATION_JOB_CACHE_TTL)
            logger.error('task_simulate_bankable_study: devis %s introuvable '
                         '(société %s)', devis_id, company_id)
            return None

        simulation = run_bankable_study(
            devis, zones=zones_etude_du_devis(devis),
            force_refresh=bool(force_refresh))
        ranger_simulation(devis.pk, simulation)

        cache.set(ckey, {
            'company_id': company_id, 'devis_id': devis_id,
            'status': 'ready', 'version': simulation.get('version'),
            'computed_at': simulation.get('computed_at'),
        }, SIMULATION_JOB_CACHE_TTL)
        logger.info('task_simulate_bankable_study OK: devis %s (%d zone(s))',
                    devis_id, len(simulation.get('zones') or []))
        return token
    except Exception as exc:  # noqa: BLE001
        cache.set(ckey, {'company_id': company_id, 'devis_id': devis_id,
                         'status': 'error', 'error': str(exc)},
                  SIMULATION_JOB_CACHE_TTL)
        logger.error('task_simulate_bankable_study failed devis=%s: %s',
                     devis_id, exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


# ── PVSYNC — resynchronisation des devis après un changement de référence ────
#
# Déclenchée par ``core.events.produit_modifie`` (émis par le viewset produit du
# Stock) via ``ventes.services.on_produit_modifie``, APRÈS commit.
#
# Volontairement SANS ``bind``/``retry``, à la différence des tâches PDF
# voisines : le service qui l'appelle sait la rejouer EN LIGNE quand le courtier
# est injoignable, et un ``self.retry`` levé hors worker ferait échouer ce repli.
# La sécurité vient d'ailleurs — l'opération est IDEMPOTENTE (rejouer le même
# événement ne modifie plus rien, cf. ``resynchroniser_devis_pour_produit``),
# donc une livraison at-least-once est sans danger.
@shared_task(
    name='ventes.resync_devis_apres_produit_modifie',
    acks_late=True,
)
def task_resync_devis_apres_produit_modifie(produit_id, company_id, champs,
                                            user_id=None):
    """Recale les devis brouillon/envoyé qui portent le produit ``produit_id``.

    Ne prend que des PK (jamais des instances) : le message survit à la file et
    à un rejeu, et le produit est RELU en base — donc jamais un objet figé au
    moment de l'émission.

    No-op silencieux si le produit ou la société a disparu entre-temps (ne
    JAMAIS relancer : réessayer ne les fera pas réapparaître).
    """
    from authentication.models import Company

    from apps.stock.models import Produit

    from .services import resynchroniser_devis_pour_produit

    company = Company.objects.filter(pk=company_id).first()
    produit = Produit.objects.filter(pk=produit_id).first()
    if company is None or produit is None:
        logger.info('task_resync_devis_apres_produit_modifie: produit %s / '
                    'société %s introuvable — rien à faire.',
                    produit_id, company_id)
        return None

    utilisateur = None
    if user_id:
        from django.contrib.auth import get_user_model
        utilisateur = get_user_model().objects.filter(pk=user_id).first()

    resultat = resynchroniser_devis_pour_produit(
        produit=produit, company=company, champs=champs, user=utilisateur)
    logger.info('task_resync_devis_apres_produit_modifie OK: produit=%s '
                'devis=%s lignes=%s', produit_id,
                resultat['devis_touches'], resultat['lignes_modifiees'])
    return resultat


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
