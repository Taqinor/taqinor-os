"""ADSENG52 — [GATED: budget fondateur ≥450 MAD/j] Adaptateur TikTok (STUB).

Minimum $50/j par campagne (vérifié). AUCUN paused-par-défaut confirmé côté
TikTok ⇒ la garde ADSENG49 (données) impose au client de FORCER PAUSED avant
toute création — la règle #3 ne peut pas dépendre d'un défaut plateforme absent.

CE STUB N'ACTIVE RIEN : chaque opération lève :class:`PlatformNotEnabledError`.
Il satisfait le contrat ``AdsPlatform`` pour que le moteur puisse le référencer,
sans qu'aucune dépense ni activation soit possible.

INVARIANT (règles #3/#4), hérité du contrat + explicite ici :
  * aucune méthode de création n'accepte ``status`` (⇒ ``TypeError``) ;
  * aucune méthode d'activation / dé-pause / resume / enable n'existe ;
  * toute création forcerait PAUSED (``forced_status``) — jamais un ACTIVE ; c'est
    la garde ADSENG49 : TikTok n'étant pas paused-par-défaut,
    ``requires_forced_paused('tiktok')`` est True et le forçage est structurel ;
  * la plateforme N'EST PAS dans la matrice ADSENG49 (GATED) : ``capabilities()``
    résout sur le défaut PRUDENT (paused-par-défaut False).
"""
from __future__ import annotations

from .base import AdsPlatform
from .capabilities import capabilities_for, requires_forced_paused


class PlatformNotEnabledError(NotImplementedError):
    """Une opération a été tentée sur un adaptateur GATED : la plateforme n'est
    ni activée ni dépensable. Sous-classe de ``NotImplementedError``."""


class TikTokPlatform(AdsPlatform):
    """Stub TikTok : implémente le contrat, n'active RIEN. TikTok n'étant pas
    paused-par-défaut, la création DOIT forcer PAUSED (garde ADSENG49)."""

    name = 'tiktok'
    # Statut de TOUTE création : PAUSED, en dur — aucune voie vers ACTIVE. C'est
    # LE point de la garde ADSENG49 pour une plateforme sans paused-par-défaut.
    forced_status = 'PAUSED'
    # Budget minimum vérifié (campagne) — donnée, pas un chemin de dépense.
    min_campaign_budget_usd_day = 50

    # ── Capacités : défaut PRUDENT (GATED ⇒ hors matrice ADSENG49) ───────────
    def capabilities(self):
        return capabilities_for(self.name)

    # ── Garde ADSENG49 : TikTok n'est pas paused-par-défaut ⇒ forçage PAUSED ──
    def _forced_create_status(self):
        """Statut imposé à toute création : ``'PAUSED'``, JAMAIS paramétrable.

        TikTok n'expose pas de paused-par-défaut confirmé, donc
        ``requires_forced_paused('tiktok')`` est True : le client force PAUSED
        avant toute création. Aucun ACTIVE n'est atteignable par cette voie —
        c'est verrouillé côté données ET côté signature (pas de kwarg ``status``)."""
        if not requires_forced_paused(self.name):
            # Ne peut survenir que si la matrice ADSENG49 marquait TikTok
            # paused-par-défaut ; on force PAUSED quoi qu'il arrive.
            return self.forced_status
        return self.forced_status

    def _gated(self, operation):
        raise PlatformNotEnabledError(
            f"Adaptateur « {self.name} » GATED (budget fondateur ≥450 MAD/j) : "
            f"l'opération « {operation} » n'est pas activée — aucune dépense "
            f"n'est possible.")

    # ── Inventaire (lecture) — gated ─────────────────────────────────────────
    def get_campaigns(self, *, fields=None, limit=None):
        self._gated('get_campaigns')

    def get_adsets(self, *, fields=None, limit=None):
        self._gated('get_adsets')

    def get_ads(self, *, fields=None, limit=None):
        self._gated('get_ads')

    def get_insights(self, object_id, *, fields=None, params=None):
        self._gated('get_insights')

    # ── Création (JAMAIS de ``status``) — force PAUSED puis reste gated ───────
    def create_campaign(self, *, name, objective, special_ad_categories=None,
                        extra_fields=None):
        self._forced_create_status()  # PAUSED forcé AVANT tout — jamais ACTIVE
        self._gated('create_campaign')

    def create_adset(self, *, name, campaign_id, extra_fields=None):
        self._forced_create_status()
        self._gated('create_adset')

    def create_ad(self, *, name, adset_id, extra_fields=None):
        self._forced_create_status()
        self._gated('create_ad')

    # ── Budgets / statut (PAUSED-only) — gated ───────────────────────────────
    def update_status_paused(self, *, object_id, level=None):
        self._gated('update_status_paused')
