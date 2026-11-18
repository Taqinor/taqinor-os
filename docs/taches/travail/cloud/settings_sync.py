"""Réglages de la session cloud pour une base « rapide » : tables créées d'un coup depuis les modèles (syncdb),
SANS rejouer les 2 399 migrations (≈ 3 h à froid). Sert au PRÉ-CONTRÔLE seulement (mise au point des specs, premier
passage des tests) ; la base qui fait foi reste celle des migrations (`tpl_test`) et la CI."""
from erp_agentique.settings.dev import *  # noqa: F401,F403


class _SansMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

    def get(self, item, default=None):
        return None


MIGRATION_MODULES = _SansMigrations()
