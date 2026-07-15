"""Selectors du module Facturation (``apps.facturation``).

Point d'entrée des LECTURES cross-app du domaine Facturation (CLAUDE.md : les
autres apps lisent ``facturation`` via ``apps.facturation.selectors`` ou par
string-FK, jamais via ``apps.facturation.models``).

Volontairement vide pour l'instant : les lectures cross-app existantes du solde
facture passent par ``apps.ventes.services``/``selectors`` (shims transitoires
ODX17). Ajouter ici une fonction de lecture fine dès qu'une autre app en aura
besoin — jamais un import direct de ``apps.facturation.models`` depuis
l'extérieur.
"""
