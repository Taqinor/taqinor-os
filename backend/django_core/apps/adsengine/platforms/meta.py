"""ADSENG48 — Adaptateur Meta : ``MetaPlatform`` enveloppe ``meta_client``.

Extraction du contrat ``AdsPlatform`` SANS aucun changement de comportement :
``MetaPlatform`` délègue FIDÈLEMENT chaque opération au ``MetaClient`` existant.
Les tests de contrat golden capturent les requêtes émises et prouvent zéro diff
avec l'appel direct au client (mêmes payloads, mêmes en-têtes).

INVARIANT PERMANENT (règles #3/#4) PRÉSERVÉ par l'extraction :

  * ``create_campaign``/``create_adset``/``create_ad`` n'exposent AUCUN
    ``status`` (délégation directe aux méthodes du client qui FORCENT PAUSED
    en dur — ``meta_client.FORCED_STATUS``) ;
  * ``update_status_paused`` reste PAUSED-only ;
  * AUCUNE méthode d'activation / dé-pause n'est ajoutée. ``__getattr__`` délègue
    au client les autres méthodes EXISTANTES (ex. ``create_ad_with_object_story_
    spec`` — elle aussi PAUSED-forcée) sans jamais en inventer une d'activation.
"""
from __future__ import annotations

from ..meta_client import MetaClient
from .base import AdsPlatform


class MetaPlatform(AdsPlatform):
    """Plateforme Meta : enveloppe fidèle de ``meta_client.MetaClient``."""

    name = 'meta'

    def __init__(self, client):
        self._client = client

    # ── Auth ─────────────────────────────────────────────────────────────────
    @classmethod
    def from_connection(cls, connection, **kwargs):
        """Construit l'adaptateur depuis une ``MetaConnection`` (token write-only)
        — même chemin que ``MetaClient.from_connection`` (aucune divergence)."""
        return cls(MetaClient.from_connection(connection, **kwargs))

    @classmethod
    def from_client(cls, client):
        """Enveloppe un ``MetaClient`` déjà construit (injection de test)."""
        return cls(client)

    # ── Capacités (ADSENG49 pilote la matrice ; repli minimal avant) ─────────
    def capabilities(self):
        try:
            from .capabilities import capabilities_for
            return capabilities_for('meta')
        except ImportError:  # ADSENG49 pas encore fondu → défaut sûr : PAUSED.
            return {'platform': 'meta', 'paused_by_default': True}

    # ── Inventaire (lecture) — délégation pure ───────────────────────────────
    def get_campaigns(self, *, fields=None, limit=None):
        return self._client.get_campaigns(fields=fields, limit=limit)

    def get_adsets(self, *, fields=None, limit=None):
        return self._client.get_adsets(fields=fields, limit=limit)

    def get_ads(self, *, fields=None, limit=None):
        return self._client.get_ads(fields=fields, limit=limit)

    def get_insights(self, object_id, *, fields=None, params=None):
        return self._client.get_insights(
            object_id, fields=fields, params=params)

    # ── Création PAUSED — délégation pure (le client FORCE PAUSED en dur) ─────
    def create_campaign(self, *, name, objective, special_ad_categories=None,
                        extra_fields=None):
        return self._client.create_campaign(
            name=name, objective=objective,
            special_ad_categories=special_ad_categories,
            extra_fields=extra_fields)

    def create_adset(self, *, name, campaign_id, extra_fields=None):
        return self._client.create_adset(
            name=name, campaign_id=campaign_id, extra_fields=extra_fields)

    def create_ad(self, *, name, adset_id, extra_fields=None):
        return self._client.create_ad(
            name=name, adset_id=adset_id, extra_fields=extra_fields)

    # ── Budgets / statut (PAUSED-only) — délégation pure ─────────────────────
    def update_status_paused(self, *, object_id, level=None):
        return self._client.update_status_paused(
            object_id=object_id, level=level)

    # ── Délégation FIDÈLE des autres méthodes EXISTANTES du client ───────────
    # (ex. ``create_ad_with_object_story_spec`` — PAUSED-forcée aussi, ``close``).
    # ``__getattr__`` n'est atteint QUE si l'attribut normal est absent ; il ne
    # peut donc jamais créer une méthode d'activation (le client n'en a aucune).
    def __getattr__(self, name):
        client = self.__dict__.get('_client')
        if client is None:
            raise AttributeError(name)
        return getattr(client, name)
