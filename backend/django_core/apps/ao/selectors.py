"""Selectors du module Appels d'offres (``apps.ao``).

Point d'entrée des LECTURES cross-app du domaine AO (CLAUDE.md : les autres
apps lisent ``ao`` via ``apps.ao.selectors`` ou par string-FK, jamais via
``apps.ao.models``).

À la sortie de compta (ODX11), AUCUNE autre app ne lit les modèles AO (aucune
string-FK ``ao.*`` hors ao) : ce module est donc volontairement vide pour
l'instant. Ajouter ici une fonction de lecture fine dès qu'une autre app en
aura besoin — jamais un import direct de ``apps.ao.models`` depuis l'extérieur.
"""
