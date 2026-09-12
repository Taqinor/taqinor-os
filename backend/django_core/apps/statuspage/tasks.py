"""NTOBS1 — job Celery beat qui rafraîchit ``ComponentStatus`` (public).

Best-effort STRICT (jamais bloquant, jamais d'exception remontée qui casserait
le beat) : une sonde en échec laisse le composant concerné sur son dernier
statut connu plutôt que de faire planter le job entier. Dérivé de
``core.health.check_services()`` — jamais un appel synchrone côté public, et
jamais de statut/texte narratif généré automatiquement (seul l'enum
opérationnel/dégradé/panne est dérivé ; le récit d'un incident reste toujours
rédigé par un humain, cf. ``models.IncidentPublic``).
"""
from celery import shared_task
from django.utils import timezone

from core.health import STATUS_DEGRADED, STATUS_DOWN, STATUS_OK, check_services

from .models import ComponentStatus

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


def _statut_ia_public():
    """« IA » — pas de sonde infra dédiée (fonctionnalité key-gated : son
    absence de clé n'est jamais une panne). ``dégradé`` seulement si
    l'introspection d'un fournisseur RÉELLEMENT sélectionné lève une
    exception (best-effort, jamais un statut inventé)."""
    try:
        from core.ai.registry import is_capability_configured
    except Exception:  # noqa: BLE001 — module IA absent/KO, jamais bloquant
        return ComponentStatus.Statut.OPERATIONAL
    for capability in ('llm', 'ocr', 'stt'):
        try:
            is_capability_configured(capability)
        except Exception:  # noqa: BLE001 — best-effort
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
    except Exception:  # noqa: BLE001 — jamais bloquant
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
            ComponentStatus.objects.update_or_create(
                nom=nom, region=PUBLIC_REGION_DEFAUT, company=None,
                defaults={'statut': statut, 'derniere_verification': now},
            )
            maj += 1
        except Exception:  # noqa: BLE001 — un composant en échec n'affecte pas les autres
            continue

    try:
        ComponentStatus.objects.update_or_create(
            nom='IA', region=PUBLIC_REGION_DEFAUT, company=None,
            defaults={
                'statut': _statut_ia_public(), 'derniere_verification': now,
            },
        )
        maj += 1
    except Exception:  # noqa: BLE001
        pass

    return maj
