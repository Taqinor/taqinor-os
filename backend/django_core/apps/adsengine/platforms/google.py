"""ADSENG50 — [GATED: budget fondateur] Adaptateur Google Ads (STUB).

Search-only, dev-token + OAuth, mutations via l'API standard Google Ads (le MCP
Google est read-only — vérifié). CE STUB N'ACTIVE RIEN et ne permet AUCUNE
dépense : chaque opération lève :class:`PlatformNotEnabledError`. Il existe pour
que le contrat ``AdsPlatform`` soit déjà satisfait (le FlightRunner peut le
référencer sans changement), mais toute action réelle est bloquée jusqu'à la
décision budget fondateur (+50–100 MAD/j additifs).

INVARIANT (règles #3/#4), hérité du contrat + explicite ici :
  * aucune méthode de création n'accepte ``status`` (⇒ ``TypeError``) ;
  * il n'existe AUCUNE méthode d'activation / dé-pause / resume / enable ;
  * toute création forcerait PAUSED (``forced_status``) — jamais un ACTIVE ;
  * la plateforme N'EST PAS dans la matrice de capacités ADSENG49 (elle reste
    GATED) : ``capabilities()`` résout sur le défaut PRUDENT (paused-par-défaut
    False ⇒ ``requires_forced_paused`` True).
"""
from __future__ import annotations

from .base import AdsPlatform
from .capabilities import capabilities_for, requires_forced_paused


class PlatformNotEnabledError(NotImplementedError):
    """Une opération a été tentée sur un adaptateur GATED : la plateforme n'est
    ni activée ni dépensable. Sous-classe de ``NotImplementedError`` (contrat
    d'échec clair, jamais un effet silencieux)."""


class GoogleAdsPlatform(AdsPlatform):
    """Stub Google Ads : implémente le contrat, n'active RIEN."""

    name = 'google'
    # Statut de TOUTE création : PAUSED, en dur — aucune voie vers ACTIVE.
    forced_status = 'PAUSED'

    # ── Capacités : défaut PRUDENT (GATED ⇒ hors matrice ADSENG49) ───────────
    def capabilities(self):
        return capabilities_for(self.name)

    # ── Garde ADSENG49 : hors matrice ⇒ forçage PAUSED requis ────────────────
    def _forced_create_status(self):
        """Statut imposé à toute création : ``'PAUSED'``, jamais paramétrable.

        ADSENG49 (données) : cette plateforme n'est pas paused-par-défaut, donc
        ``requires_forced_paused(name)`` est True et le client DOIT forcer PAUSED.
        On renvoie ``forced_status`` quoi qu'il arrive — aucun ACTIVE possible."""
        requires_forced_paused(self.name)  # lecture du garde (data-driven)
        return self.forced_status

    def _gated(self, operation):
        raise PlatformNotEnabledError(
            f"Adaptateur « {self.name} » GATED (décision budget fondateur) : "
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
        self._forced_create_status()
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
