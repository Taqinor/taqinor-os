"""ADSENG29 — Arbitrage DCO (Dynamic Creative Optimization) — creative-sci §e.

STATUT (PUB25, 2026-07-19) — NON CÂBLÉ en production : aucun appelant hors tests.
Pas un doublon. EN ATTENTE DE : un flux de création qui consulte cet arbitre au
bootstrap cold-start (le DCO natif Meta reste réservé au démarrage à froid et
n'est déclenché par aucun chemin de génération/lancement aujourd'hui). Capacité
prête + testée ; jamais mort silencieux.

Le DCO natif de Meta est réservé au **bootstrap de démarrage à froid** (aucune
donnée) : Meta assemble automatiquement image/vidéo/texte pour amorcer un
signal, mais expose UN SEUL ad par ad set et une attribution par asset limitée.
Dès qu'un signal existe, on repasse à la **rotation multi-ads discrète**
(ADSENG25) où le bandit a une attribution par bras.

INVARIANT STRUCTUREL (dd-creative-sci §e — vérifié) : **exclusion mutuelle
DCO ↔ rotation multi-ads par ad set**. Un ad set DCO ne porte qu'UN ad ; un ad
set en rotation en porte plusieurs — les deux ne coexistent jamais.

CHOIX D'IMPLÉMENTATION (voir rapport de lane) : cette exclusion N'EST PAS une
contrainte de MODÈLE — l'``is_dynamic_creative`` vit côté Meta (pas sur
``AdSetMirror``, qui n'a pas de champ « mode ») et l'inscrire exigerait une
MIGRATION, interdite dans cette lane. Elle est donc une **validation au niveau
SERVICE** : un invariant validé et testé ici (``validate_mutual_exclusion``),
appliqué à chaque choix de mode — jamais une garde silencieuse. Les plafonds
d'assets DCO natifs sont eux aussi validés (``validate_dco_asset_spec``).
"""
from __future__ import annotations

import dataclasses
import logging

logger = logging.getLogger(__name__)

# ── Plafonds d'assets DCO natifs (dd-creative-sci §e — vérifiés) ─────────────
DCO_MAX_IMAGES = 10
DCO_MAX_VIDEOS = 10
DCO_MAX_BODIES = 5          # textes principaux
DCO_MAX_TITLES = 5          # titres
DCO_MAX_DESCRIPTIONS = 5    # descriptions
DCO_MAX_CTAS = 5            # types d'appel à l'action
DCO_MAX_LINKS = 5           # liens
DCO_MAX_TOTAL_ASSETS = 30   # total tous champs confondus
DCO_ADS_PER_ADSET = 1       # UN seul ad par ad set en DCO

# Plafond par champ de la spec DCO (clé de spec → plafond).
_FIELD_CAPS = {
    'images': DCO_MAX_IMAGES,
    'videos': DCO_MAX_VIDEOS,
    'bodies': DCO_MAX_BODIES,
    'titles': DCO_MAX_TITLES,
    'descriptions': DCO_MAX_DESCRIPTIONS,
    'ctas': DCO_MAX_CTAS,
    'links': DCO_MAX_LINKS,
}

# ── Modes créatifs mutuellement exclusifs par ad set ─────────────────────────
MODE_DCO_BOOTSTRAP = 'dco_bootstrap'
MODE_MULTI_AD_ROTATION = 'multi_ad_rotation'
MODES = (MODE_DCO_BOOTSTRAP, MODE_MULTI_AD_ROTATION)


class DcoModeConflict(ValueError):
    """Violation de l'exclusion mutuelle DCO ↔ rotation multi-ads."""


class DcoCapExceeded(ValueError):
    """Un plafond d'assets DCO natif est dépassé."""


@dataclasses.dataclass(frozen=True)
class ModeDecision:
    """Choix EXPLICITE de mode créatif pour UN ad set."""

    adset_ref: object
    mode: str
    is_cold_start: bool
    reason_fr: str


def adset_has_signal(adset):
    """Vrai si l'ad set a déjà un signal (dépense ou résultat > 0).

    Démarrage à FROID = aucun signal → éligible au bootstrap DCO. Lit les
    ``InsightSnapshot`` rattachés (FK générique). Dégrade à ``False`` (froid)
    si l'ad set est ``None`` ou n'a aucun instantané.
    """
    if adset is None:
        return False
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q
    from .models import InsightSnapshot

    ct = ContentType.objects.get_for_model(adset.__class__)
    return InsightSnapshot.objects.filter(
        company=adset.company, content_type=ct, object_id=adset.pk,
    ).filter(Q(spend__gt=0) | Q(results__gt=0)).exists()


def validate_dco_asset_spec(spec):
    """Valide les plafonds d'assets d'une spec DCO native.

    ``spec`` : dict de listes par champ (``images``/``videos``/``bodies``/…).
    Lève ``DcoCapExceeded`` (raisons FR) si un champ dépasse son plafond ou si
    le total dépasse 30. Renvoie le total d'assets si valide.
    """
    spec = spec or {}
    violations = []
    total = 0
    for field, cap in _FIELD_CAPS.items():
        count = len(spec.get(field, []) or [])
        total += count
        if count > cap:
            violations.append(
                f"{field} : {count} > plafond {cap}.")
    if total > DCO_MAX_TOTAL_ASSETS:
        violations.append(
            f"total : {total} > plafond {DCO_MAX_TOTAL_ASSETS} assets.")
    if violations:
        raise DcoCapExceeded(
            "Plafonds DCO dépassés — " + " ".join(violations))
    return total


def validate_mutual_exclusion(*, mode, existing_ad_count=0,
                              is_dynamic_creative=None):
    """Invariant SERVICE : exclusion mutuelle DCO ↔ rotation multi-ads.

    * ``MODE_DCO_BOOTSTRAP`` sur un ad set qui porte déjà >1 ad → conflit (le
      DCO n'expose qu'UN ad par ad set).
    * ``MODE_MULTI_AD_ROTATION`` sur un ad set déjà marqué DCO
      (``is_dynamic_creative=True``) → conflit.

    Lève ``DcoModeConflict`` (raison FR) en cas de violation ; renvoie ``mode``
    sinon.
    """
    if mode not in MODES:
        raise DcoModeConflict(
            f"Mode inconnu « {mode} » (attendu : {' / '.join(MODES)}).")
    if mode == MODE_DCO_BOOTSTRAP and int(existing_ad_count or 0) > 1:
        raise DcoModeConflict(
            "DCO impossible : l'ad set porte déjà plusieurs ads (le DCO "
            "n'expose qu'un seul ad par ad set) — exclusion mutuelle avec la "
            "rotation multi-ads.")
    if mode == MODE_MULTI_AD_ROTATION and is_dynamic_creative:
        raise DcoModeConflict(
            "Rotation multi-ads impossible : l'ad set est en DCO "
            "(is_dynamic_creative) — exclusion mutuelle.")
    return mode


def plan_adset_creative_mode(adset, *, requested_mode=None,
                             existing_ad_count=0, is_dynamic_creative=None,
                             cold_start=None):
    """Choix EXPLICITE et validé du mode créatif d'un ad set.

    Détermine le démarrage à froid (``cold_start`` explicite, sinon
    ``adset_has_signal``). Par défaut : DCO au bootstrap à froid, rotation
    multi-ads dès qu'un signal existe. Un ``requested_mode`` est honoré mais
    VALIDÉ : le DCO est réservé au démarrage à froid (bootstrap ONLY) et
    l'exclusion mutuelle est appliquée. Renvoie une ``ModeDecision``.
    """
    is_cold = cold_start if cold_start is not None else not adset_has_signal(
        adset)
    default_mode = (MODE_DCO_BOOTSTRAP if is_cold
                    else MODE_MULTI_AD_ROTATION)
    mode = requested_mode or default_mode

    if mode == MODE_DCO_BOOTSTRAP and not is_cold:
        # DCO = bootstrap SEULEMENT : refusé s'il y a déjà un signal.
        raise DcoModeConflict(
            "DCO réservé au démarrage à froid (bootstrap uniquement) : cet ad "
            "set a déjà un signal — passez en rotation multi-ads.")
    validate_mutual_exclusion(
        mode=mode, existing_ad_count=existing_ad_count,
        is_dynamic_creative=is_dynamic_creative)

    if mode == MODE_DCO_BOOTSTRAP:
        reason = ("Démarrage à froid (aucun signal) — bootstrap DCO pour "
                  "amorcer, un seul ad par ad set.")
    else:
        reason = ("Signal présent — rotation multi-ads discrète (attribution "
                  "par bras pour le bandit).")
    return ModeDecision(
        adset_ref=getattr(adset, 'pk', None) or getattr(
            adset, 'id', None) or adset,
        mode=mode, is_cold_start=is_cold, reason_fr=reason)
