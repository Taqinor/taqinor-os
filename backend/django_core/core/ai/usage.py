"""NTAI1 — Journal d'usage & coût des capacités IA (couche FONDATION).

Ce module mesure ce que l'IA consomme : un appel réel à une capacité
(``complete``/``extract``/``transcribe``/``inspect``) laisse une ligne portant
la capacité, le fournisseur, la feature appelante, les jetons, le coût estimé,
la latence et le succès. **Aucune valeur de prompt ni de donnée métier n'est
enregistrée** — uniquement des métriques.

DEUX CONTRAINTES D'ARCHITECTURE, et comment elles sont tenues :

1. ``core`` est une couche de base : elle n'importe AUCUNE app métier. Le
   modèle de persistance (``ai_governance.LlmUsageRecord``) vit donc dans son
   app, et ``core`` ne connaît qu'un **puits** (« sink ») enregistré au
   démarrage par ``apps.ai_governance`` — exactement le patron déjà utilisé par
   ``ai_governance.drift.register_distribution_provider``. Sans puits
   enregistré, :func:`record_usage` est un no-op complet.

2. Un fournisseur IA ne connaît pas la société de l'appelant (il reçoit un
   prompt, pas une requête). La société est donc portée par un **contexte**
   (:func:`usage_context`, un ``ContextVar``) posé par la couche appelante
   (vue/tâche). **Hors contexte, rien n'est enregistré** : on ne devine JAMAIS
   une société — une ligne mal scopée serait pire que pas de ligne.

Le coût, lui, n'est jamais inventé : il n'est calculé que si un TARIF est
explicitement configuré pour le fournisseur (``settings.AI_TOKEN_COSTS``).
Sinon le montant vaut 0 **et** ``tarife=False`` dit que c'est un coût INCONNU,
pas un coût nul.
"""
from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings

logger = logging.getLogger(__name__)

#: Capacités journalisées (miroir des clés du registre).
USAGE_CAPABILITIES = ('ocr', 'stt', 'vision_qa', 'llm')


# ─────────────────────────────────────────────────────────────────────────────
# Contexte d'appel (qui appelle, pour quelle société)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class UsageContext:
    """Société + feature à l'origine de l'appel IA en cours."""

    company_id: int | None = None
    feature_key: str = ''


_EMPTY_CONTEXT = UsageContext()
_CONTEXT: contextvars.ContextVar[UsageContext] = contextvars.ContextVar(
    'core.ai.usage.context', default=_EMPTY_CONTEXT)


def current_context() -> UsageContext:
    """Contexte d'usage courant (vide par défaut — jamais ``None``)."""
    return _CONTEXT.get() or _EMPTY_CONTEXT


def set_context(*, company_id=None, feature_key: str = ''):
    """Pose le contexte et renvoie le JETON à rendre à :func:`reset_context`.

    Forme « manuelle » pour les appelants dont l'entrée et la sortie sont dans
    deux méthodes différentes (une vue DRF : ``initial()`` puis
    ``finalize_response()``). Partout ailleurs, préférer :func:`usage_context`.
    """
    if company_id is not None and not isinstance(company_id, int):
        company_id = getattr(company_id, 'pk', None) or getattr(
            company_id, 'id', None)
    return _CONTEXT.set(UsageContext(
        company_id=company_id, feature_key=str(feature_key or '')[:120]))


def reset_context(token) -> None:
    """Restaure le contexte précédent — tolère un jeton absent/déjà rendu."""
    if token is None:
        return
    try:
        _CONTEXT.reset(token)
    except ValueError:  # jeton créé dans un autre contexte (thread/tâche)
        _CONTEXT.set(_EMPTY_CONTEXT)


@contextmanager
def usage_context(*, company_id=None, feature_key: str = ''):
    """Pose la société + la feature pour la durée du bloc.

    ``company_id`` accepte un id ou un objet portant ``.id``/``.pk`` (une
    ``Company``) — la couche appelante passe ce qu'elle a sous la main.
    Ré-entrant : le contexte précédent est restauré à la sortie, même en cas
    d'exception (``ContextVar.reset``)."""
    token = set_context(company_id=company_id, feature_key=feature_key)
    try:
        yield
    finally:
        reset_context(token)


# ─────────────────────────────────────────────────────────────────────────────
# Puits d'écriture (enregistré par apps.ai_governance)
# ─────────────────────────────────────────────────────────────────────────────

_SINKS: list = []


def register_usage_sink(fn):
    """Enregistre un puits ``fn(**metriques)`` appelé à chaque usage IA.

    Utilisable en décorateur. Idempotent : ré-enregistrer la même fonction
    (rechargement d'app en test) ne la duplique pas."""
    if fn not in _SINKS:
        _SINKS.append(fn)
    return fn


def unregister_usage_sink(fn) -> None:
    """Retire un puits (tests)."""
    if fn in _SINKS:
        _SINKS.remove(fn)


def usage_sinks() -> list:
    """Puits actuellement enregistrés (copie)."""
    return list(_SINKS)


# ─────────────────────────────────────────────────────────────────────────────
# Coût estimé — JAMAIS inventé
# ─────────────────────────────────────────────────────────────────────────────

def token_rates(provider: str) -> dict | None:
    """Tarif configuré du fournisseur, ou ``None`` s'il n'y en a pas.

    ``settings.AI_TOKEN_COSTS`` : ``{clé_fournisseur: {'prompt': <MAD/1k>,
    'completion': <MAD/1k>}}``. Absent = coût inconnu (et non coût nul)."""
    table = getattr(settings, 'AI_TOKEN_COSTS', None) or {}
    rates = table.get(provider)
    if not isinstance(rates, dict):
        return None
    return rates


def _decimal(valeur) -> Decimal:
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def estimate_cost(provider: str, prompt_tokens: int,
                  completion_tokens: int) -> tuple[Decimal, bool]:
    """``(montant_mad, tarife)`` pour un appel.

    ``tarife=False`` signifie « aucun tarif configuré pour ce fournisseur » :
    le montant renvoyé vaut alors 0 mais ce **n'est pas** un coût nul, c'est un
    coût INCONNU. L'agrégation le signale au lieu d'afficher un total qui
    mentirait (règle « zéro chiffre inventé »)."""
    rates = token_rates(provider)
    if not rates:
        return Decimal('0'), False
    montant = (
        _decimal(rates.get('prompt')) * Decimal(int(prompt_tokens or 0))
        + _decimal(rates.get('completion')) * Decimal(int(completion_tokens or 0))
    ) / Decimal('1000')
    return montant.quantize(Decimal('0.000001')), True


def tokens_from_result(result) -> tuple[int, int]:
    """Jetons rapportés par le fournisseur dans ``AIResult.data['usage']``.

    On ne les ESTIME jamais (pas de « longueur / 4 ») : un fournisseur qui ne
    rapporte pas sa consommation laisse 0, et l'agrégat le dit."""
    data = getattr(result, 'data', None) or {}
    usage = data.get('usage') if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return 0, 0

    def _int(valeur):
        try:
            return max(0, int(valeur))
        except (TypeError, ValueError):
            return 0

    return (_int(usage.get('prompt_tokens')),
            _int(usage.get('completion_tokens')))


# ─────────────────────────────────────────────────────────────────────────────
# Enregistrement d'un usage
# ─────────────────────────────────────────────────────────────────────────────

def record_usage(*, capability: str, provider: str, prompt_tokens: int = 0,
                 completion_tokens: int = 0, latency_ms: int = 0,
                 success: bool = True, company_id=None, feature_key: str = '',
                 error: str = '') -> bool:
    """Journalise UN appel IA. Best-effort : ne lève JAMAIS.

    Renvoie ``True`` si au moins un puits a accepté la ligne. Sans société
    connue (ni argument ni contexte) ou sans puits enregistré : no-op silencieux
    — on n'écrit pas une ligne qu'on ne saurait pas scoper."""
    contexte = current_context()
    if company_id is None:
        company_id = contexte.company_id
    if company_id is None or not _SINKS:
        return False
    if capability not in USAGE_CAPABILITIES:
        return False

    provider = str(provider or 'noop')
    cout, tarife = estimate_cost(provider, prompt_tokens, completion_tokens)
    charge = {
        'company_id': company_id,
        'capability': capability,
        'provider': provider,
        'feature_key': str(feature_key or contexte.feature_key or '')[:120],
        'prompt_tokens': max(0, int(prompt_tokens or 0)),
        'completion_tokens': max(0, int(completion_tokens or 0)),
        'cost_estimated': cout,
        'cout_tarife': tarife,
        'latency_ms': max(0, int(latency_ms or 0)),
        'success': bool(success),
        'error': str(error or '')[:255],
    }
    ecrit = False
    for sink in list(_SINKS):
        try:
            sink(**charge)
            ecrit = True
        except Exception:  # noqa: BLE001 — le journal ne casse jamais l'appel
            logger.warning('core.ai.usage: puits en échec (%s)',
                           getattr(sink, '__name__', sink), exc_info=True)
    return ecrit


# ─────────────────────────────────────────────────────────────────────────────
# NTAI2 — statut de budget (fourni par apps.ai_governance)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BudgetStatus:
    """Situation budgétaire IA d'une société pour le mois courant.

    ``configured=False`` = aucun budget actif défini : rien n'est bridé et
    aucun chiffre n'est affiché (on ne compare pas à un plafond imaginaire)."""

    configured: bool = False
    plafond: Decimal = Decimal('0')
    depense: Decimal = Decimal('0')
    pourcentage: float = 0.0
    depasse: bool = False
    alerte: bool = False
    periode: str = ''

    def as_dict(self) -> dict:
        return {
            'configure': self.configured,
            'plafond_mad': str(self.plafond),
            'depense_mad': str(self.depense),
            'pourcentage': round(self.pourcentage, 2),
            'depasse': self.depasse,
            'alerte': self.alerte,
            'periode': self.periode,
        }


_STATS_PROVIDER = None


def register_usage_stats_provider(fn):
    """Enregistre le calculateur de métriques ``fn(company) -> dict``.

    Utilisé par NTAI6 (tableau de santé des capacités) : ``core`` ne sait pas
    lire le journal, il demande à l'app qui le détient."""
    global _STATS_PROVIDER
    _STATS_PROVIDER = fn
    return fn


def capability_metrics(company) -> dict:
    """``{capacité: {appels, latence_p50_ms, derniere_erreur, derniere_erreur_le}}``.

    Dict VIDE si aucun calculateur n'est enregistré ou si la société est
    inconnue : l'écran affiche alors « aucune mesure », jamais un zéro
    trompeur."""
    if _STATS_PROVIDER is None or company is None:
        return {}
    try:
        mesures = _STATS_PROVIDER(company)
    except Exception:  # noqa: BLE001 — l'état des capacités ne casse jamais
        logger.warning('core.ai.usage: métriques indisponibles', exc_info=True)
        return {}
    return mesures if isinstance(mesures, dict) else {}


_BUDGET_PROVIDER = None


def register_budget_provider(fn):
    """Enregistre le calculateur de budget ``fn(company) -> BudgetStatus``."""
    global _BUDGET_PROVIDER
    _BUDGET_PROVIDER = fn
    return fn


def budget_provider():
    """Calculateur de budget enregistré (ou ``None``)."""
    return _BUDGET_PROVIDER


def budget_status(company) -> BudgetStatus:
    """Statut budgétaire de ``company`` — jamais d'exception.

    Sans calculateur enregistré (app absente/désinstallée), renvoie un statut
    ``configured=False`` : aucune feature n'est bridée."""
    fn = _BUDGET_PROVIDER
    if fn is None or company is None:
        return BudgetStatus()
    try:
        statut = fn(company)
    except Exception:  # noqa: BLE001 — un budget illisible ne coupe rien
        logger.warning('core.ai.usage: statut de budget indisponible',
                       exc_info=True)
        return BudgetStatus()
    return statut if isinstance(statut, BudgetStatus) else BudgetStatus()
