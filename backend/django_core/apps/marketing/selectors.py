"""Selectors du module Marketing (``apps.marketing``).

Point d'entrée des LECTURES cross-app du domaine marketing (CLAUDE.md : les
autres apps lisent marketing via ``apps.marketing.selectors`` ou par string-FK,
jamais via ``apps.marketing.models``).

À la sortie de compta (ODX9/ODX10), AUCUNE autre app ne lit les modèles
marketing (aucune string-FK ``marketing.*`` hors marketing, vérifié) : ce
module est donc volontairement vide pour l'instant. Ajouter ici une fonction
de lecture fine dès qu'une autre app en aura besoin — jamais un import direct
de ``apps.marketing.models`` depuis l'extérieur.
"""
