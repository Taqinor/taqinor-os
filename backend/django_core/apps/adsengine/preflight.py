"""ADSENG38 — Préflight d'AUTONOMIE + go-live (la porte structurelle).

Agrège TOUTES les portes qui doivent être vertes AVANT que le mode autonome
puisse s'activer. Tant qu'une seule porte est rouge, ``activate`` REFUSE de poser
le drapeau d'autonomie (garantie STRUCTURELLE — impossible d'activer sans que
tout soit vert) et renvoie la liste FR de ce qui manque. Verte partout = le mode
est ACTIVABLE, mais reste **OFF par défaut** (l'activation est un geste explicite,
jamais automatique).

Les 8 portes (dd-science-core §d + le tour complet P1-P5) :

  1. ``loop``               — la boucle ENG12 est verte (connexion Meta live) ;
  2. ``guardrails``         — les garde-fous sont posés (``GuardrailConfig``) ;
  3. ``alerts``             — les alertes sont câblées (≥1 ``RulePolicy`` active) ;
  4. ``backlog_volume``     — le volume de backlog approuvé est suffisant ;
  5. ``backlog_diversity``  — la diversité d'accroches atteint le plancher ;
  6. ``plan``               — un plan de vol validé (ACTIF) existe ;
  7. ``simulation``         — la simulation ADSENG36 a été revue OK (acquittée) ;
  8. ``field_tests``        — les 7 inconnues terrain (ADSENG37) sont tranchées.

Ce module est de la LOGIQUE d'agrégation pure (aucune vue HTTP ici — la checklist
verte/rouge de P7, ADSENG40, appellera ``status``). Multi-tenant : la société est
toujours passée explicitement et jamais élargie.

NOTA (distinct d'ENG19) : approuver une action (``adsengine_approve``) et ACTIVER
l'autonomie (``adsengine_autonomy_toggle``, ADSENG47) sont deux pouvoirs séparés —
l'autonomie est admin-seul.
"""
from __future__ import annotations

import dataclasses
import logging

from django.core.cache import cache

from . import backlog as backlog_mod
from . import field_tests, flightplan, flightrunner
from .models import FlightPlan, GuardrailConfig, MetaConnection, RulePolicy

logger = logging.getLogger(__name__)

# Acquittement de la simulation (revue humaine du run ADSENG36 en P7) — cache,
# jamais un champ modèle. 30 j de TTL ; révocable.
SIM_ACK_TTL = 60 * 60 * 24 * 30


class AutonomyNotReady(Exception):
    """Levée par ``activate`` quand une porte manque : porte le détail FR."""

    def __init__(self, missing_fr):
        self.missing_fr = list(missing_fr)
        super().__init__("Autonomie non activable : " + " ".join(self.missing_fr))


@dataclasses.dataclass
class Gate:
    """Une porte de préflight : clé, état, libellé FR, et ce qui manque (FR)."""

    key: str
    ok: bool
    label_fr: str
    detail_fr: str = ''


# ── Acquittement de simulation (cache par société) ────────────────────────────
def _sim_ack_key(company):
    return f'adsengine:sim_ack:{company.pk}'


def acknowledge_simulation(company):
    """Marque la simulation ADSENG36 comme REVUE OK pour la société (geste
    humain en P7 — ADSENG44 montre le run, l'opérateur acquitte)."""
    cache.set(_sim_ack_key(company), True, SIM_ACK_TTL)


def revoke_simulation_ack(company):
    cache.delete(_sim_ack_key(company))


def simulation_acknowledged(company):
    return bool(cache.get(_sim_ack_key(company)))


def field_tests_complete():
    """Vrai UNIQUEMENT si les 7 inconnues terrain (ADSENG37) sont toutes
    tranchées (aucune constante ne reste en source=recherche)."""
    return not field_tests.pending_keys()


# ── Agrégation des portes ─────────────────────────────────────────────────────
def gates(company, *, today=None):
    """Évalue et renvoie la liste ordonnée des ``Gate`` pour une société."""
    conn = MetaConnection.objects.filter(company=company, enabled=True).first()
    loop_ok = bool(conn and conn.is_live)

    guardrails_ok = GuardrailConfig.objects.filter(company=company).exists()
    alerts_ok = RulePolicy.objects.filter(
        company=company, enabled=True).exists()

    volume = flightplan.approved_backlog_count(company, today=today)
    volume_ok = volume >= flightplan.PREFLIGHT_BACKLOG_MIN
    diversity_ok = backlog_mod.meets_diversity_floor(company, today=today)
    diversity = backlog_mod.hook_diversity(company, today=today)

    plan_ok = FlightPlan.objects.filter(
        company=company, status=FlightPlan.Statut.ACTIF).exists()
    sim_ok = simulation_acknowledged(company)
    ft_ok = field_tests_complete()

    return [
        Gate('loop', loop_ok, "Boucle ENG12 verte (connexion Meta active)",
             '' if loop_ok else "Aucune connexion Meta active + tokenisée."),
        Gate('guardrails', guardrails_ok, "Garde-fous posés",
             '' if guardrails_ok else "Aucune GuardrailConfig pour la société."),
        Gate('alerts', alerts_ok, "Alertes câblées",
             '' if alerts_ok else "Aucune règle de garde-fou activée."),
        Gate('backlog_volume', volume_ok, "Volume de backlog suffisant",
             '' if volume_ok else
             (f"Backlog insuffisant : {volume} créatif(s) approuvé(s) "
              f"(minimum {flightplan.PREFLIGHT_BACKLOG_MIN}).")),
        Gate('backlog_diversity', diversity_ok, "Diversité d'accroches atteinte",
             '' if diversity_ok else
             (f"Diversité insuffisante : {diversity} accroche(s) distincte(s) "
              f"(minimum {backlog_mod.DIVERSITY_FLOOR_HOOKS}).")),
        Gate('plan', plan_ok, "Plan de vol validé (actif)",
             '' if plan_ok else "Aucun plan de vol validé et actif."),
        Gate('simulation', sim_ok, "Simulation ADSENG36 revue OK",
             '' if sim_ok else
             "Simulation non revue/acquittée (voir la visionneuse P7)."),
        Gate('field_tests', ft_ok, "Tests terrain (7 inconnues) tranchés",
             '' if ft_ok else
             (f"Inconnues terrain non tranchées : "
              f"{', '.join(field_tests.pending_keys())}.")),
    ]


def status(company, *, today=None):
    """Statut de préflight d'autonomie de la société.

    Renvoie ``{'ready': bool, 'active': bool, 'gates': [...], 'missing_fr':
    [...]}``. ``ready`` = toutes les portes vertes (⇒ ACTIVABLE, mais OFF tant
    que ``activate`` n'est pas appelé). ``active`` = l'autonomie est réellement
    activée pour la société (drapeau posé)."""
    gate_list = gates(company, today=today)
    missing = [
        (g.detail_fr or g.label_fr) for g in gate_list if not g.ok]
    ready = not missing
    return {
        'ready': ready,
        'active': flightrunner.is_autonomy_active(company),
        'gates': [dataclasses.asdict(g) for g in gate_list],
        'missing_fr': missing,
    }


# ── Activation / désactivation (la garantie structurelle) ─────────────────────
def activate(company, *, today=None):
    """ACTIVE le mode autonome — UNIQUEMENT si toutes les portes sont vertes.

    Garantie STRUCTURELLE : si une seule porte manque, lève ``AutonomyNotReady``
    (avec la liste FR de ce qui manque) et NE POSE PAS le drapeau. Impossible
    d'activer l'autonomie tant que le préflight n'est pas entièrement vert."""
    st = status(company, today=today)
    if not st['ready']:
        raise AutonomyNotReady(st['missing_fr'])
    flightrunner.set_autonomy_active(company, True)
    logger.info('preflight: autonomie ACTIVÉE société=%s (toutes portes vertes)',
                company.pk)
    st['active'] = True
    return st


def deactivate(company):
    """Désactive le mode autonome (retire le drapeau). Toujours autorisé —
    couper l'autonomie ne demande aucune porte verte (sécurité)."""
    flightrunner.set_autonomy_active(company, False)
    logger.info('preflight: autonomie DÉSACTIVÉE société=%s', company.pk)
    return {'active': False}


def is_active(company):
    """Vrai si l'autonomie est activée pour la société (OFF par défaut)."""
    return flightrunner.is_autonomy_active(company)
