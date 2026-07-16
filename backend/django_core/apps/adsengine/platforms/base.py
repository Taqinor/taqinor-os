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


def normalize_insight_row(row):
    """Normalise UNE ligne d'insight brute (dict plateforme) → une forme
    AGNOSTIQUE : ``{spend, results, impressions, clicks, frequency, cpl,
    date_start, raw}``. Les nombres sont des floats (jamais un None silencieux
    caché dans une chaîne). ``raw`` conserve la ligne d'origine (traçabilité)."""
    row = row or {}
    spend = _to_float(row.get('spend'), 0.0)
    results = _to_float(row.get('results'), 0.0)
    cpl = row.get('cpl')
    cpl = _to_float(cpl) if cpl is not None else (
        (spend / results) if results else None)
    return {
        'spend': spend,
        'results': results,
        'impressions': _to_float(row.get('impressions'), 0.0),
        'clicks': _to_float(row.get('clicks'), 0.0),
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
