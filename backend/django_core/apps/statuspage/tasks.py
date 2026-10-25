"""NTOBS1 — job Celery beat qui rafraîchit ``ComponentStatus`` (public).

Best-effort STRICT (jamais bloquant, jamais d'exception remontée qui casserait
le beat) : une sonde en échec laisse le composant concerné sur son dernier
statut connu plutôt que de faire planter le job entier. Dérivé de
``core.health.check_services()`` — jamais un appel synchrone côté public, et
jamais de statut/texte narratif généré automatiquement (seul l'enum
opérationnel/dégradé/panne est dérivé ; le récit d'un incident reste toujours
rédigé par un humain, cf. ``models.IncidentPublic``).
"""
import logging
from celery import shared_task
from django.utils import timezone

from core.health import STATUS_DEGRADED, STATUS_DOWN, STATUS_OK, check_services

from .models import ComponentStatus, ComponentStatusLog, UptimeDayBucket

logger = logging.getLogger(__name__)

# Composants PUBLICS vendus au client (jamais les noms de sonde internes bruts
# tels que « database »/« broker », qui exposeraient l'architecture). Chaque
# composant public agrège le PIRE statut des sondes internes qui le composent.
PUBLIC_COMPONENT_PROBES = {
    'API': ('database', 'cache'),
    'PDF-devis': ('storage', 'database'),
    'Stockage documents': ('storage',),
    'Notifications': ('broker', 'queue'),
}

_PROBE_TO_PUBLIC = {
    STATUS_OK: ComponentStatus.Statut.OPERATIONAL,
    STATUS_DEGRADED: ComponentStatus.Statut.DEGRADED,
    STATUS_DOWN: ComponentStatus.Statut.MAJOR_OUTAGE,
}

# Ordre de gravité croissant — utilisé pour l'agrégation « pire des sondes ».
_ORDRE_GRAVITE = [
    ComponentStatus.Statut.OPERATIONAL,
    ComponentStatus.Statut.DEGRADED,
    ComponentStatus.Statut.PARTIAL_OUTAGE,
    ComponentStatus.Statut.MAJOR_OUTAGE,
]

PUBLIC_REGION_DEFAUT = 'EU-West/Hetzner'


def _pire_statut_public(statuts):
    pire = ComponentStatus.Statut.OPERATIONAL
    for statut in statuts:
        if _ORDRE_GRAVITE.index(statut) > _ORDRE_GRAVITE.index(pire):
            pire = statut
    return pire


def _poser_statut_composant(nom, statut, now):
    """Pose le statut courant du composant SYSTÈME ``nom`` et renvoie l'ancien.

    ``(nom, region, company=NULL)`` ne peut PAS être unique en base (NULL
    distincts) : ``update_or_create`` levait MultipleObjectsReturned dès que
    deux lignes existaient et le composant ne se rafraîchissait plus. On
    reprend la plus ancienne ligne, sans jamais en créer une seconde."""
    ligne = (
        ComponentStatus.objects
        .filter(nom=nom, region=PUBLIC_REGION_DEFAUT, company=None)
        .order_by('pk').first())
    if ligne is None:
        ComponentStatus.objects.create(
            nom=nom, region=PUBLIC_REGION_DEFAUT, company=None,
            statut=statut, derniere_verification=now)
        return None
    ancien = ligne.statut
    ligne.statut = statut
    ligne.derniere_verification = now
    ligne.save(update_fields=['statut', 'derniere_verification', 'updated_at'])
    return ancien


def _logger_changement_statut(nom, region, ancien, nouveau):
    """NTOBS33 — journalise un changement RÉELLEMENT détecté (jamais un tick
    inchangé, jamais bloquant si l'écriture échoue)."""
    try:
        ComponentStatusLog.objects.create(
            company=None, composant=nom, region=region,
            ancien_statut=ancien or '', nouveau_statut=nouveau)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning("tasks._logger_changement_statut : erreur ignorée (mode dégradé)", exc_info=True)


def _accumuler_uptime_jour(nom, region, statut, now):
    """NTOBS14 — accumule le tick courant dans le bucket du JOUR (créé au
    premier tick du jour, mis à jour à chaque tick suivant). ``ComponentStatus``
    n'étant qu'un état COURANT (pas un historique), ce bucket EST la seule
    trace exploitable de la journée — jamais une exception remontée
    (best-effort, un échec d'agrégation n'affecte jamais le statut public)."""
    try:
        # ``company__isnull=True`` (et non ``company=None``) : c'est le terme de la condition de
        # ``statuspage_uptimebucket_jour_systeme`` (ENF18) -- la création laisse ``company`` NULL.
        bucket, _created = UptimeDayBucket.objects.get_or_create(
            company__isnull=True, composant=nom, region=region, date=now.date(),
            defaults={'statut_pire_du_jour': statut},
        )
        if _ORDRE_GRAVITE.index(statut) > _ORDRE_GRAVITE.index(
                bucket.statut_pire_du_jour):
            bucket.statut_pire_du_jour = statut
        bucket.echantillons_total += 1
        if statut == ComponentStatus.Statut.OPERATIONAL:
            bucket.echantillons_operationnels += 1
        bucket.pct_disponible_jour = round(
            100.0 * bucket.echantillons_operationnels / bucket.echantillons_total,
            2)
        bucket.save(update_fields=[
            'statut_pire_du_jour', 'echantillons_total',
            'echantillons_operationnels', 'pct_disponible_jour', 'updated_at',
        ])
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning("tasks._accumuler_uptime_jour : erreur ignorée (mode dégradé)", exc_info=True)


def _statut_ia_public():
    """« IA » — pas de sonde infra dédiée (fonctionnalité key-gated : son
    absence de clé n'est jamais une panne). ``dégradé`` seulement si
    l'introspection d'un fournisseur RÉELLEMENT sélectionné lève une
    exception (best-effort, jamais un statut inventé)."""
    try:
        from core.ai.registry import is_capability_configured
    except Exception:  # noqa: BLE001 — module IA absent/KO, jamais bloquant (D-ENF22-BLE001)
        logger.warning("tasks._statut_ia_public : erreur ignorée (mode dégradé)", exc_info=True)
        return ComponentStatus.Statut.OPERATIONAL
    for capability in ('llm', 'ocr', 'stt'):
        try:
            is_capability_configured(capability)
        except Exception:  # noqa: BLE001 — best-effort (D-ENF22-BLE001)
            logger.warning("tasks._statut_ia_public : erreur ignorée (mode dégradé)", exc_info=True)
            return ComponentStatus.Statut.DEGRADED
    return ComponentStatus.Statut.OPERATIONAL


@shared_task(name='statuspage.rafraichir_composants')
def rafraichir_composants():
    """NTOBS1 — rafraîchit les ``ComponentStatus`` publics (beat 5 min).

    Renvoie le nombre de composants effectivement mis à jour (0 si
    ``check_services()`` échoue entièrement — jamais une exception remontée
    au scheduler)."""
    try:
        services = check_services()
    except Exception:  # noqa: BLE001 — jamais bloquant (D-ENF22-BLE001)
        logger.warning("tasks.rafraichir_composants : erreur ignorée (mode dégradé)", exc_info=True)
        return 0

    par_nom = {s['name']: s['status'] for s in services}
    now = timezone.now()
    maj = 0

    for nom, sondes in PUBLIC_COMPONENT_PROBES.items():
        statuts_public = [
            _PROBE_TO_PUBLIC.get(
                par_nom.get(sonde), ComponentStatus.Statut.OPERATIONAL)
            for sonde in sondes
        ]
        statut = _pire_statut_public(statuts_public)
        try:
            ancien = _poser_statut_composant(nom, statut, now)
            maj += 1
            if ancien != statut:
                _logger_changement_statut(
                    nom, PUBLIC_REGION_DEFAUT, ancien, statut)
        except Exception:  # noqa: BLE001 — un composant en échec n'affecte pas les autres (D-ENF22-BLE001)
            logger.warning("tasks.rafraichir_composants : erreur ignorée (mode dégradé)", exc_info=True)
            continue
        _accumuler_uptime_jour(nom, PUBLIC_REGION_DEFAUT, statut, now)

    statut_ia = _statut_ia_public()
    try:
        ancien_ia = _poser_statut_composant('IA', statut_ia, now)
        maj += 1
        if ancien_ia != statut_ia:
            _logger_changement_statut(
                'IA', PUBLIC_REGION_DEFAUT, ancien_ia, statut_ia)
    except Exception:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
        logger.warning("tasks.rafraichir_composants : erreur ignorée (mode dégradé)", exc_info=True)
    _accumuler_uptime_jour('IA', PUBLIC_REGION_DEFAUT, statut_ia, now)

    return maj
