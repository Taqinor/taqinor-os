"""La LISTE des calepinages sert aussi ``compteurs_statut`` : les effectifs par statut
pour les puces de l'écran, en UNE requête groupée (``services/lecture_liste.py``).

Les effectifs suivent la recherche et les filtres de la liste mais PAS le filtre de
statut (une puce « Brouillon » active ne fait pas tomber les autres à zéro), et la
même portée que la liste : société de l'appelant et vue restreinte au responsable,
car la requête est celle de ``get_queryset``.
"""
from __future__ import annotations

from ..services.lecture_liste import compteurs_statut

__all__ = ['ListeCompteursMixin']


class ListeCompteursMixin:
    """Ajoute ``compteurs_statut`` à la réponse paginée de ``list``."""

    #: Posé le temps du calcul des effectifs : ``get_queryset`` ignore alors ``?statut=``.
    sans_filtre_statut = False

    def list(self, request, *args, **kwargs):
        reponse = super().list(request, *args, **kwargs)
        if isinstance(reponse.data, dict):
            self.sans_filtre_statut = True
            try:
                reponse.data['compteurs_statut'] = compteurs_statut(self.get_queryset())
            finally:
                self.sans_filtre_statut = False
        return reponse
