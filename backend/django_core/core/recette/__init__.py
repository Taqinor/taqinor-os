"""CIQ625 — ``core.recette`` : les règles PURES de la recette d'un chantier.

Partagées par ``apps.installations`` (la fiche ``CommissioningRecord``, seule
propriétaire de la recette d'un chantier — CIQ6) et ``apps.ventes``
(``commissioning.py``, FG274), qui ne peuvent pas s'importer l'une l'autre
(frontière inter-apps). Même arbitrage que ``core.pompage`` : la règle vit en
FONDATION, stdlib seule, aucune dépendance Django, aucun ``apps.*``.
"""
