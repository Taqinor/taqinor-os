"""Sélecteurs LECTURE SEULE du module Gestion de flotte.

Point d'entrée des LECTURES cross-app vers la flotte. Les autres apps ne lisent
jamais les modèles flotte directement : elles passent par ces fonctions, toutes
scopées par société (CLAUDE.md, règle de modularité cross-app).
"""
from .models import EnginRoulant, Vehicule


def vehicules_de_la_societe(company):
    """Tous les véhicules d'une société (queryset scopé)."""
    return Vehicule.objects.filter(company=company)


def engins_de_la_societe(company):
    """Tous les engins roulants d'une société (queryset scopé)."""
    return EnginRoulant.objects.filter(company=company)
