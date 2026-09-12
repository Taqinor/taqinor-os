"""Lectures du module GRC & Conformité (NTGRC).

Point d'entrée UNIQUE de lecture pour les autres apps. Toute fonction est
bornée à une société (multi-tenant) — jamais de lecture cross-société.
"""
from __future__ import annotations
