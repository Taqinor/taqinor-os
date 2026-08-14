"""Services (écriture/orchestration) de planification supply chain (Groupe
NTSCM). Toute lecture cross-app (``apps.stock``, ``apps.ventes``…) passe par
le ``selectors.py``/``services.py`` de l'app cible, jamais un import de
modèle — voir chaque fonction pour le détail de sa frontière.
"""
