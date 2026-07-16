"""ADSENG48 — Paquet ``platforms`` : le contrat abstrait ``AdsPlatform`` + ses
adaptateurs concrets (Meta aujourd'hui). Le FlightRunner et le bandit ne parlent
qu'au contrat — jamais à un client concret — pour que d'autres plateformes
s'ajoutent sans toucher au moteur.
"""
from .base import AdsPlatform, normalize_insight_row  # noqa: F401
from .meta import MetaPlatform  # noqa: F401

__all__ = ['AdsPlatform', 'MetaPlatform', 'normalize_insight_row']
