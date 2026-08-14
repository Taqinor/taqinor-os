"""Sélecteurs (LECTURE) du module « conversation_ai » (Groupe NTAI).

Point d'entrée UNIQUE des lectures cross-app : une autre app qui a besoin des
appels commerciaux appelle ces fonctions, jamais les modèles de ce module.
Toute lecture est SCOPÉE SOCIÉTÉ — aucune fonction n'expose une requête non
filtrée.
"""
from __future__ import annotations


def appels_for_company(company):
    """Tous les appels commerciaux d'une société (queryset scopé)."""
    from .models import AppelCommercial

    return AppelCommercial.objects.filter(company=company)


def appels_for_lead(company, lead_id):
    """Appels rattachés à un lead donné, scopés société."""
    return appels_for_company(company).filter(lead_id=lead_id)


def appels_transcrits(company):
    """Appels dont la transcription a abouti (base des analyses)."""
    from .models import AppelCommercial

    return appels_for_company(company).filter(
        statut=AppelCommercial.STATUT_TRANSCRIT)
