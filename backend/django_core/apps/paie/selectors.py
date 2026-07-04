"""Sélecteurs (lectures) de la paie, exposés aux autres apps.

Lecture seule — jamais d'écriture ici. D'autres apps (rh…) lisent la paie
UNIQUEMENT via ce module (jamais ``apps.paie.models`` directement), symétrique
au patron ``apps.rh.selectors`` déjà en place pour le sens inverse.
"""
from .models import AvanceSalarie


def solde_avance(avance_id):
    """Solde restant dû d'une ``AvanceSalarie`` par id (YHIRE5, cross-app).

    Sélecteur de lecture pour ``rh`` : le guichet de demande RH
    (``rh.AvanceSalaire``) affiche le solde réel de l'avance MATÉRIALISÉE
    côté paie (le seul moteur câblé au bulletin) sans jamais importer
    ``paie.models``. Renvoie ``None`` si l'id est inconnu.
    """
    avance = AvanceSalarie.objects.filter(pk=avance_id).first()
    if avance is None:
        return None
    return avance.solde_restant
