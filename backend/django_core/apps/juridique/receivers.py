"""Abonnements de ``apps.juridique`` au bus d'événements ``core.events`` (M6).

Branché depuis ``JuridiqueConfig.ready()``. Reste vide tant qu'aucune réaction
inter-app n'est câblée (NTJUR26 y pose l'abonnement à
``dossier_juridique_clos``).
"""
from __future__ import annotations
