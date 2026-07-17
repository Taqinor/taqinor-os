"""ADSENG48 — Le contrat abstrait ``AdsPlatform`` (extrait de ``meta_client``).

Une plateforme publicitaire expose SIX surfaces : auth, inventaire (lecture),
création PAUSED, budgets/statut, insights normalisés, capacités. Le FlightRunner
et le bandit ne parlent QU'À ce contrat — jamais à un client concret — donc une
autre plateforme s'ajoute sans toucher au moteur.

INVARIANT PERMANENT (règles #3/#4), porté par le CONTRAT lui-même :

  * AUCUNE méthode de création n'accepte de ``status`` (le passer lève
    ``TypeError``) — toute création naît PAUSED ;
  * il n'existe AUCUNE méthode d'activation / dé-pause / resume / enable ;
  * ``update_status_paused`` ne pose que PAUSED (jamais paramétrable).

Ces propriétés sont vérifiées par les tests de contrat golden sur l'adaptateur
Meta (zéro diff de comportement avec ``meta_client``).
"""
from __future__ import annotations

import abc


def _to_float(value, default=None):
    """Convertit une valeur d'insight brute en float (``default`` si illisible)."""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ── ADSDEEP1 — types d'actions Meta (AdsActionStats) mappés en colonnes typées.
# Références : dossier adsdeep-insights-api §1. « conversations » = la métrique
# CTWA canonique (une par fenêtre glissante 7 j) ; « lead » = TOUS les leads.
ACTION_CONVERSATIONS = 'onsite_conversion.messaging_conversation_started_7d'
ACTION_LEAD = 'lead'
ACTION_LINK_CLICK = 'link_click'

# Champs vidéo Meta (tous en forme AdsActionStats — listes de dicts, PAS des
# scalaires). Il n'existe DÉLIBÉRÉMENT PAS de champ « video_3_sec » chez Meta :
# les seuils réels documentés sont 6s/15s/30s + les quartiles p25→p100.
_VIDEO_FIELDS = {
    'p25': 'video_p25_watched_actions',
    'p50': 'video_p50_watched_actions',
    'p75': 'video_p75_watched_actions',
    'p95': 'video_p95_watched_actions',
    'p100': 'video_p100_watched_actions',
    'plays': 'video_play_actions',
    's6': 'video_6_sec_watched_actions',
    's15': 'video_15_sec_watched_actions',
    's30': 'video_30_sec_watched_actions',
    'thruplay': 'video_thruplay_watched_actions',
    'avg_time': 'video_avg_time_watched_actions',
}


def action_value(actions, action_type):
    """Somme la (les) valeur(s) d'un ``action_type`` dans un tableau
    ``AdsActionStats`` (``[{action_type, value, <fenêtre>_click, …}]``).

    Renvoie ``None`` si aucune entrée du type n'existe (distinct d'un vrai 0 —
    permet à l'appelant de laisser la colonne NULL plutôt que d'inventer un 0).
    Robuste aux valeurs illisibles (ignorées) et à un ``actions`` non-liste."""
    if not isinstance(actions, (list, tuple)):
        return None
    total = None
    for item in actions:
        if not isinstance(item, dict):
            continue
        if item.get('action_type') != action_type:
            continue
        val = _to_float(item.get('value'))
        if val is None:
            continue
        total = (total or 0.0) + val
    return total


def _video_metrics(row):
    """Extrait le dict des métriques vidéo depuis les champs AdsActionStats de
    ``row`` (dossier insights-api §3). Ne garde que les clés RÉELLEMENT
    présentes (une ad statique → dict vide) ; chaque valeur est le total du
    tableau AdsActionStats correspondant."""
    metrics = {}
    for key, field in _VIDEO_FIELDS.items():
        # Les champs vidéo ont un action_type variable (video_view…) : on somme
        # toutes les entrées de la liste plutôt que de filtrer par type.
        val = _sum_action_values(row.get(field))
        if val is not None:
            metrics[key] = val
    return metrics


def _sum_action_values(actions):
    """Somme toutes les ``value`` d'un tableau AdsActionStats (tous types
    confondus) — pour les champs vidéo dont le type d'action est variable.
    ``None`` si vide/illisible."""
    if not isinstance(actions, (list, tuple)):
        return None
    total = None
    for item in actions:
        if not isinstance(item, dict):
            continue
        val = _to_float(item.get('value'))
        if val is None:
            continue
        total = (total or 0.0) + val
    return total


def normalize_insight_row(row):
    """Normalise UNE ligne d'insight brute (dict plateforme) → une forme
    AGNOSTIQUE : ``{spend, results, impressions, reach, clicks, link_clicks,
    conversations, leads_count, video_metrics, frequency, cpl, date_start,
    raw}``. Les nombres sont des floats (jamais un None silencieux caché dans une
    chaîne). ``raw`` conserve la ligne d'origine (traçabilité).

    ADSDEEP1 — les champs de conversion (``conversations``/``leads_count``) et
    ``link_clicks`` sont extraits du tableau ``actions[]`` (AdsActionStats) quand
    ils n'ont pas de colonne scalaire dédiée ; ``video_metrics`` agrège les
    champs vidéo AdsActionStats."""
    row = row or {}
    spend = _to_float(row.get('spend'), 0.0)
    results = _to_float(row.get('results'), 0.0)
    cpl = row.get('cpl')
    cpl = _to_float(cpl) if cpl is not None else (
        (spend / results) if results else None)
    actions = row.get('actions')
    # link_clicks : préfère la colonne scalaire ``inline_link_clicks`` (toujours
    # présente sur un compte non ventilé), repli sur l'action ``link_click``.
    link_clicks = _to_float(row.get('inline_link_clicks'))
    if link_clicks is None:
        link_clicks = action_value(actions, ACTION_LINK_CLICK)
    return {
        'spend': spend,
        'results': results,
        'impressions': _to_float(row.get('impressions'), 0.0),
        'reach': _to_float(row.get('reach')),
        'clicks': _to_float(row.get('clicks'), 0.0),
        'link_clicks': link_clicks,
        'conversations': action_value(actions, ACTION_CONVERSATIONS),
        'leads_count': action_value(actions, ACTION_LEAD),
        'video_metrics': _video_metrics(row),
        'frequency': _to_float(row.get('frequency')),
        'cpl': cpl,
        'date_start': row.get('date_start'),
        'raw': dict(row),
    }


class AdsPlatform(abc.ABC):
    """Contrat abstrait d'une plateforme publicitaire.

    ``name`` identifie la plateforme (``'meta'``…). Toutes les méthodes de
    création n'ont **aucun** paramètre ``status`` — c'est la première ligne de
    défense de l'invariant PAUSED (le langage lève ``TypeError`` sur un
    ``status=`` glissé). Aucune méthode d'activation n'est déclarée : elle
    n'existe donc nulle part dans la hiérarchie.
    """

    name = 'abstract'

    # ── Capacités (ADSENG49 — pilotent les gardes) ───────────────────────────
    @abc.abstractmethod
    def capabilities(self):
        """Matrice de capacités de la plateforme (paused-par-défaut, budgets
        minimum, granularité des insights…). DONNÉES, pas de la logique."""

    # ── Inventaire (lecture) ─────────────────────────────────────────────────
    @abc.abstractmethod
    def get_campaigns(self, *, fields=None, limit=None):
        """Liste des campagnes du compte."""

    @abc.abstractmethod
    def get_adsets(self, *, fields=None, limit=None):
        """Liste des ad sets du compte."""

    @abc.abstractmethod
    def get_ads(self, *, fields=None, limit=None):
        """Liste des ads du compte."""

    @abc.abstractmethod
    def get_insights(self, object_id, *, fields=None, params=None):
        """Insights BRUTS d'un objet (liste de dicts plateforme)."""

    # ── Création PAUSED (JAMAIS de ``status``) ───────────────────────────────
    @abc.abstractmethod
    def create_campaign(self, *, name, objective, special_ad_categories=None,
                        extra_fields=None):
        """Crée une campagne — TOUJOURS PAUSED (aucun ``status`` acceptable)."""

    @abc.abstractmethod
    def create_adset(self, *, name, campaign_id, extra_fields=None):
        """Crée un ad set — TOUJOURS PAUSED."""

    @abc.abstractmethod
    def create_ad(self, *, name, adset_id, extra_fields=None):
        """Crée une ad — TOUJOURS PAUSED."""

    # ── Budgets / statut (PAUSED-only) ───────────────────────────────────────
    @abc.abstractmethod
    def update_status_paused(self, *, object_id, level=None):
        """Met un objet en PAUSED — et RIEN d'autre (aucun ``status``
        paramétrable ; impossible d'activer par cette voie)."""

    # ── Insights normalisés (concret, agnostique plateforme) ─────────────────
    def normalized_insights(self, object_id, *, fields=None, params=None):
        """Insights d'un objet, NORMALISÉS (forme agnostique — cf.
        :func:`normalize_insight_row`). S'appuie sur ``get_insights`` : un
        adaptateur ne réimplémente que la lecture brute."""
        rows = self.get_insights(object_id, fields=fields, params=params)
        return [normalize_insight_row(r) for r in (rows or [])]

    def paused_by_default(self):
        """Raccourci : la plateforme crée-t-elle en PAUSED par défaut ? (lu de la
        matrice de capacités). Une plateforme sans paused-défaut ⇒ la garde force
        PAUSED côté adaptateur (ADSENG49)."""
        return bool((self.capabilities() or {}).get('paused_by_default'))
