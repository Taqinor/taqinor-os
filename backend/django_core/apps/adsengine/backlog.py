"""ADSENG27 — Gestion du backlog créatif (dd-creative-sci §c).

Le backlog (``CreativeBacklogItem``) est le STOCK 3-6 mois de créatifs prêts,
comme données. Ce module calcule :
  * le **runway** — semaines restantes au rythme du plan (un ajout/semaine par
    défaut, aligné sur la ration de rotation ADSENG25) ;
  * l'**alerte « backlog bas »** quand le runway passe sous 3 semaines
    (indicateur avancé — jamais un échec silencieux, leçon Madgicx) ;
  * le **plancher de diversité** — ≥4 accroches DISTINCTES sur 3 mois (un
    backlog de 12 recombinaisons d'une seule accroche = fausse diversité) ;
  * la **file** par campagne cible, ordonnée par date-au-plus-tôt puis tag
    saisonnier.

Logique de lecture pure (aucune écriture Meta). L'``EngineAlert`` réel
(WhatsApp) est rendu/émis ailleurs (gated) ; on renvoie ici un descripteur.
"""
from __future__ import annotations

import datetime

from .models import CreativeBacklogItem

# Un ajout de challenger par semaine (ration ADSENG25) — rythme par défaut.
DEFAULT_WEEKLY_RATE = 1

# Seuil « backlog bas » : sous 3 semaines de runway.
LOW_BACKLOG_WEEKS = 3

# Plancher de diversité : ≥4 accroches distinctes sur la fenêtre.
DIVERSITY_FLOOR_HOOKS = 4
DIVERSITY_WINDOW_DAYS = 90  # 3 mois


def _base_queue(company, *, campaign=None):
    """Items EN FILE de la société (option : pour une campagne cible)."""
    qs = CreativeBacklogItem.objects.filter(
        company=company, status=CreativeBacklogItem.Statut.EN_FILE)
    if campaign is not None:
        qs = qs.filter(target_campaign=campaign)
    return qs


def _earliest_le_q(day):
    """``Q`` : ``earliest_date`` nulle OU ≤ ``day`` (import local de
    ``django.db.models`` pour ne rien importer au chargement du module)."""
    from django.db.models import Q
    return Q(earliest_date__isnull=True) | Q(earliest_date__lte=day)


def _ready_now(qs, today):
    """Items publiables MAINTENANT : date-au-plus-tôt nulle ou atteinte."""
    return qs.filter(_earliest_le_q(today))


def ready_count(company, *, today=None, campaign=None, ready_only=False):
    """Nombre d'items publiables maintenant. ``ready_only`` limite aux
    assets dont la policy est validée (créatifs réellement diffusables)."""
    today = today or datetime.date.today()
    qs = _ready_now(_base_queue(company, campaign=campaign), today)
    if ready_only:
        qs = qs.filter(asset__policy_stamp__passed=True)
    return qs.count()


def compute_runway(company, *, weekly_rate=DEFAULT_WEEKLY_RATE, today=None,
                   campaign=None):
    """Runway en SEMAINES : items publiables maintenant ÷ rythme hebdomadaire.

    ``weekly_rate`` ≤ 0 est traité comme 1 (garde anti-division par zéro).
    """
    rate = weekly_rate if weekly_rate and weekly_rate > 0 else 1
    count = ready_count(company, today=today, campaign=campaign)
    return count / float(rate)


def is_backlog_low(company, *, weekly_rate=DEFAULT_WEEKLY_RATE, today=None,
                   threshold_weeks=LOW_BACKLOG_WEEKS, campaign=None):
    """Vrai si le runway est sous le seuil (3 semaines par défaut)."""
    runway = compute_runway(
        company, weekly_rate=weekly_rate, today=today, campaign=campaign)
    return runway < threshold_weeks


def hook_diversity(company, *, window_days=DIVERSITY_WINDOW_DAYS, today=None):
    """Nombre d'accroches DISTINCTES (``asset__hook_id`` non vide) dans la file
    sur la fenêtre glissante (date-au-plus-tôt nulle ou dans la fenêtre)."""
    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=window_days)
    qs = _base_queue(company).filter(_earliest_le_q(horizon))
    hooks = (qs.exclude(asset__hook_id='')
               .values_list('asset__hook_id', flat=True)
               .distinct())
    return len({h for h in hooks if h})


def meets_diversity_floor(company, *, floor=DIVERSITY_FLOOR_HOOKS,
                          window_days=DIVERSITY_WINDOW_DAYS, today=None):
    """Vrai si le plancher de diversité (≥4 accroches/3 mois) est atteint."""
    return hook_diversity(
        company, window_days=window_days, today=today) >= floor


def queue_for_campaign(company, campaign, *, today=None):
    """File ordonnée (date-au-plus-tôt puis tag saisonnier) pour une campagne
    cible — TOUS les items EN FILE programmés (y compris datés dans le futur),
    la file complète à visualiser/planifier. ``today`` est accepté pour une
    signature cohérente mais n'exclut rien (le runway, lui, filtre le prêt-
    maintenant)."""
    qs = _base_queue(company, campaign=campaign)
    return list(qs.order_by('earliest_date', 'seasonal_tag', 'id'))


def backlog_alert(company, *, weekly_rate=DEFAULT_WEEKLY_RATE, today=None,
                  campaign=None):
    """Descripteur d'alerte backlog (rendu WhatsApp ailleurs, gated).

    Renvoie ``should_alert`` vrai si le backlog est bas OU si la diversité est
    sous le plancher, avec un message FR et les chiffres. Ne crée AUCUNE ligne
    ``EngineAlert`` (son type ne couvre pas le backlog) — c'est un descripteur.
    """
    today = today or datetime.date.today()
    runway = compute_runway(
        company, weekly_rate=weekly_rate, today=today, campaign=campaign)
    low = runway < LOW_BACKLOG_WEEKS
    diversity = hook_diversity(company, today=today)
    diversity_ok = diversity >= DIVERSITY_FLOOR_HOOKS
    parts = []
    if low:
        parts.append(
            f"Backlog bas : {runway:.1f} semaine(s) de runway restantes "
            f"(seuil {LOW_BACKLOG_WEEKS}).")
    if not diversity_ok:
        parts.append(
            f"Diversité insuffisante : {diversity} accroche(s) distincte(s) "
            f"sur 3 mois (plancher {DIVERSITY_FLOOR_HOOKS}).")
    return {
        'should_alert': bool(low or not diversity_ok),
        'severity': 'warning',
        'runway_weeks': runway,
        'backlog_low': low,
        'diversity': diversity,
        'diversity_ok': diversity_ok,
        'message': ' '.join(parts),
    }
