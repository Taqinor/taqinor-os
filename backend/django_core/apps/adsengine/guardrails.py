"""ENG3/ENG9 — Garde-fous du moteur publicitaire.

RÈGLE PERMANENTE (extension de la règle #3 « les campagnes naissent PAUSED ») :
le moteur ne peut **JAMAIS** activer une campagne. L'activation n'est pas un
champ de ``GuardrailConfig`` et ``enforce()`` lève TOUJOURS sur une transition
vers un statut ACTIF — quelle que soit la config, sans aucun opt-in possible.

ENG9 étoffe ce module :
  * checks PRÉ-APPLY — plafond quotidien, ±variation hebdomadaire, PAUSED-only,
    jamais d'activation ;
  * détecteur d'ANOMALIE — dépense > 0 ET 0 résultat sur ``anomaly_window_hours``
    → crée une ``EngineAction`` « proposer pause » + une ALERTE.

LEÇON MADGICX n°1 (fil rouge d'ENG9) : **une règle qui ne peut PAS tourner ALERTE
au lieu d'échouer en silence**. Chaque check qui rencontre une entrée manquante
(config absente, budget courant inconnu…) lève ``GuardrailInoperative`` ET émet
une alerte via ``emit_alert`` — jamais un ``return`` silencieux qui laisserait
croire que le garde-fou a validé.
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

# Statuts considérés comme une ACTIVATION (interdite). On normalise en MAJUSCULES
# et on couvre le libellé Meta (``ACTIVE``) comme le français (``ACTIF``).
ACTIVE_STATUSES = frozenset({'ACTIVE', 'ACTIF'})

# Types d'alerte du moteur (réutilisés par ENG13 ``EngineAlert``).
ALERT_ANOMALY = 'anomalie'
ALERT_GUARDRAIL = 'garde_fou'
ALERT_INOPERATIVE = 'regle_inoperante'
# PUB20 — token Meta mort (code 190) détecté par une tâche de synchro.
ALERT_TOKEN_INVALID = 'token_invalide'


class GuardrailViolation(Exception):
    """Levée quand une action viole un garde-fou — elle n'est JAMAIS appliquée."""


class GuardrailInoperative(GuardrailViolation):
    """Levée quand un garde-fou ne PEUT PAS s'évaluer (entrée manquante).

    Sous-classe de ``GuardrailViolation`` : une règle inopérante bloque l'action
    au même titre qu'une violation (fail-safe), MAIS émet en plus une alerte
    « règle inopérante » — jamais un échec silencieux (leçon Madgicx n°1)."""


def enforce(*, target_status, config=None):
    """Vérifie qu'une transition de statut de campagne est permise.

    Lève ``GuardrailViolation`` sur TOUTE transition vers un statut actif
    (``ACTIVE``/``ACTIF``), **indépendamment** de ``config`` : aucun réglage ne
    peut autoriser une activation par le moteur (invariant permanent). Renvoie
    ``True`` pour tout autre statut (``PAUSED``, etc.).

    ``config`` (``GuardrailConfig`` optionnel) est accepté pour une signature
    stable — il est délibérément IGNORÉ pour la règle d'activation ; ENG9 s'en
    servira pour les autres garde-fous (plafond, variation, anomalie).
    """
    normalized = str(target_status or '').strip().upper()
    if normalized in ACTIVE_STATUSES:
        raise GuardrailViolation(
            "Activation d'une campagne interdite : le moteur ne peut jamais "
            "activer une campagne (règle permanente — aucune configuration ne "
            "l'autorise)."
        )
    return True


# ── ENG9 — Hook d'alerte (branché réellement par ENG13 ``EngineAlert``) ───────
def emit_alert(company, *, alert_type, message, action=None, detail=None):
    """Émet une alerte moteur (garde-fou / anomalie / règle inopérante).

    HOOK ENG9→ENG13 (désormais BRANCHÉ) : journalise TOUJOURS (jamais un échec
    silencieux) PUIS matérialise un ``EngineAlert`` via ``alerts.create_alert``.
    ``action`` (optionnel) relie l'alerte à la proposition ``EngineAction`` ;
    ``detail`` porte un contexte JSON. Renvoie l'``EngineAlert`` créé, ou ``None``
    si aucune société n'est fournie (chemins de test purs).

    La persistance est best-effort : une erreur d'écriture d'alerte ne doit
    jamais faire échouer la règle de garde-fou elle-même (elle est déjà
    journalisée)."""
    logger.warning(
        'adsengine ALERTE [%s] société=%s: %s',
        alert_type, getattr(company, 'pk', company), message)
    if company is None:
        return None
    try:
        from .alerts import create_alert
        return create_alert(
            company, alert_type=alert_type, message=message,
            action=action, detail=detail)
    except Exception:  # pragma: no cover - défensif, l'alerte est déjà loggée
        logger.warning('adsengine: échec persistance EngineAlert', exc_info=True)
        return None


# ── ENG9 — Checks PRÉ-APPLY ───────────────────────────────────────────────────
def enforce_never_activate(target_status, *, company=None):
    """Alias explicite d'``enforce`` (jamais d'activation). Émet une alerte
    garde-fou sur violation avant de relancer (délégué à ``enforce`` pour la
    logique ; l'alerte rend la violation visible pour le dashboard ENG13)."""
    try:
        return enforce(target_status=target_status)
    except GuardrailViolation as exc:
        if company is not None:
            emit_alert(company, alert_type=ALERT_GUARDRAIL, message=str(exc))
        raise


def enforce_paused_only(target_status, *, company=None):
    """PAUSED-only : le moteur ne propose QUE des transitions vers PAUSED.

    Lève ``GuardrailViolation`` pour tout statut cible non vide autre que
    ``PAUSED`` (a fortiori toute activation). Un statut vide (aucune transition
    de statut demandée) est permis. Émet une alerte sur violation."""
    normalized = str(target_status or '').strip().upper()
    if normalized and normalized != 'PAUSED':
        msg = (
            f"Transition de statut « {normalized} » refusée : le moteur ne "
            f"propose que des transitions vers PAUSED (jamais d'activation).")
        if company is not None:
            emit_alert(company, alert_type=ALERT_GUARDRAIL, message=msg)
        raise GuardrailViolation(msg)
    return True


def check_daily_ceiling(config, daily_budget_mad, *, company=None):
    """Plafond de dépense quotidienne : le budget quotidien proposé ne peut
    dépasser ``config.daily_budget_ceiling_mad``.

    Config absente OU budget illisible → ``GuardrailInoperative`` + alerte
    (la règle ne PEUT PAS s'évaluer : on bloque, on ne skip jamais en silence)."""
    if config is None:
        return _inoperative(
            company, "Plafond quotidien non évaluable : aucune GuardrailConfig "
                     "pour la société.")
    try:
        budget = float(daily_budget_mad)
    except (TypeError, ValueError):
        return _inoperative(
            company, "Plafond quotidien non évaluable : budget quotidien "
                     "proposé illisible.")
    ceiling = config.daily_budget_ceiling_mad
    if budget > ceiling:
        msg = (
            f"Budget quotidien {budget:g} MAD > plafond {ceiling} MAD "
            f"(garde-fou société).")
        if company is not None:
            emit_alert(company, alert_type=ALERT_GUARDRAIL, message=msg)
        raise GuardrailViolation(msg)
    return True


def check_weekly_change(config, *, current_budget, new_budget, company=None):
    """Variation hebdomadaire max : |Δ%| entre budget courant et proposé ne peut
    dépasser ``config.weekly_change_pct_max`` (dans les deux sens).

    Config absente, budget courant absent/≤0, ou budgets illisibles →
    ``GuardrailInoperative`` + alerte (jamais un skip silencieux)."""
    if config is None:
        return _inoperative(
            company, "Variation hebdomadaire non évaluable : aucune "
                     "GuardrailConfig pour la société.")
    try:
        current = float(current_budget)
        proposed = float(new_budget)
    except (TypeError, ValueError):
        return _inoperative(
            company, "Variation hebdomadaire non évaluable : budgets illisibles.")
    if current <= 0:
        return _inoperative(
            company, "Variation hebdomadaire non évaluable : budget courant "
                     "inconnu ou nul (aucune base de comparaison).")
    change_pct = abs(proposed - current) / current * 100.0
    limit = config.weekly_change_pct_max
    if change_pct > limit:
        msg = (
            f"Variation de budget {change_pct:.1f}% > maximum hebdomadaire "
            f"{limit}% (garde-fou société).")
        if company is not None:
            emit_alert(company, alert_type=ALERT_GUARDRAIL, message=msg)
        raise GuardrailViolation(msg)
    return True


def _inoperative(company, message):
    """Chemin commun « règle inopérante » : alerte PUIS lève (jamais silencieux)."""
    if company is not None:
        emit_alert(company, alert_type=ALERT_INOPERATIVE, message=message)
    raise GuardrailInoperative(message)


# ── ENG9 — Détecteur d'anomalie (dépense > 0 ET 0 résultat) ───────────────────
def _window_start_date(now, hours):
    """Date de début de fenêtre : ``now`` (date) moins ``hours`` convertis en
    jours (les instantanés d'insight sont datés au JOUR). Fenêtre minimale 1 j."""
    days = max(1, round((hours or 0) / 24.0))
    base = now if isinstance(now, datetime.date) else datetime.date.today()
    return base - datetime.timedelta(days=days - 1)


def detect_anomalies(company, *, now=None, config=None):
    """ENG9 — Détecte les cibles « dépense > 0 ET 0 résultat » sur la fenêtre.

    Pour chaque miroir (campagne/adset/ad) de la société, agrège spend + results
    des ``InsightSnapshot`` sur ``anomaly_window_hours`` : si la dépense cumulée
    est > 0 mais que les résultats cumulés valent 0 (ou None), c'est une anomalie
    → on CRÉE une ``EngineAction`` « proposer pause » (jamais appliquée : elle
    attend l'approbation humaine) ET on émet une ALERTE.

    Idempotent-safe : si une proposition de pause OUVERTE (proposée) existe déjà
    pour la même cible, on ne la duplique pas (et on n'alerte pas à nouveau).

    Config absente → on ALERTE (règle dégradée) et on tourne quand même avec la
    fenêtre par défaut (48 h) : jamais un skip silencieux (leçon Madgicx n°1).

    Renvoie la liste des ``EngineAction`` de pause nouvellement créées.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from . import services
    from .models import (
        AdCampaignMirror, AdMirror, AdSetMirror, EngineAction, GuardrailConfig,
        InsightSnapshot,
    )

    if config is None:
        config = GuardrailConfig.objects.filter(company=company).first()
    if config is None:
        window_hours = 48
        emit_alert(
            company, alert_type=ALERT_INOPERATIVE,
            message="Détection d'anomalie dégradée : aucune GuardrailConfig — "
                    "fenêtre par défaut 48 h appliquée.")
    else:
        window_hours = config.anomaly_window_hours

    start = _window_start_date(now, window_hours)
    created = []

    for model in (AdCampaignMirror, AdSetMirror, AdMirror):
        ct = ContentType.objects.get_for_model(model)
        for mirror in model.objects.filter(company=company):
            agg = (InsightSnapshot.objects
                   .filter(company=company, content_type=ct,
                           object_id=mirror.pk, date__gte=start)
                   .aggregate(spend=Sum('spend'), results=Sum('results')))
            spend = agg['spend'] or 0
            results = agg['results'] or 0
            if spend > 0 and results == 0:
                action = _propose_pause(
                    company, mirror, model, ct, services, EngineAction)
                if action is not None:
                    created.append(action)
                    emit_alert(
                        company, alert_type=ALERT_ANOMALY,
                        message=(
                            f"Anomalie : {mirror.meta_id} a dépensé "
                            f"{spend} MAD pour 0 résultat depuis le {start} — "
                            f"pause proposée."),
                        action=action,
                        detail={'target_meta_id': mirror.meta_id,
                                'spend': str(spend)})
    return created


_TARGET_TYPE_FOR_MODEL = {
    'AdCampaignMirror': 'campaign',
    'AdSetMirror': 'adset',
    'AdMirror': 'ad',
}


def _propose_pause(company, mirror, model, ct, services, EngineAction):
    """Crée UNE proposition de pause pour ``mirror`` si aucune n'est déjà ouverte.

    Renvoie l'action créée, ou ``None`` si une proposition de pause proposée
    existe déjà pour la même cible (déduplication, idempotence des runs)."""
    target_type = _TARGET_TYPE_FOR_MODEL[model.__name__]
    existing = EngineAction.objects.filter(
        company=company, kind=EngineAction.Kind.PAUSE,
        status=EngineAction.Statut.PROPOSEE,
        payload__target_object_id=mirror.pk,
        payload__target_type=target_type).exists()
    if existing:
        return None
    return services.propose_action(
        company, kind=EngineAction.Kind.PAUSE,
        reason_fr=(
            f"Mettre en pause {target_type} {mirror.meta_id} : dépense sans "
            f"aucun résultat sur la fenêtre d'observation (anomalie)."),
        payload={
            'target_type': target_type,
            'target_meta_id': mirror.meta_id,
            'target_object_id': mirror.pk,
        })
