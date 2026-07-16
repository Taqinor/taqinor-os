"""Selectors du module Achats (``apps.achats``).

Point d'entrée des LECTURES cross-app du domaine Achats (CLAUDE.md : les autres
apps lisent ``achats`` via ``apps.achats.selectors`` ou par string-FK, jamais via
``apps.achats.models``).

Volontairement vide pour l'instant : aucune autre app ne lit finement les
modèles achats fournisseurs (les lectures existantes passent par
``apps.stock.selectors``/``services``, shims transitoires ODX19). Ajouter ici une
fonction de lecture fine dès qu'une autre app en aura besoin — jamais un import
direct de ``apps.achats.models`` depuis l'extérieur.
"""
