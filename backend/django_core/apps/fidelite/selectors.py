"""Sélecteurs LECTURE SEULE du domaine Fidélité exposés aux AUTRES apps.

Point d'entrée cross-app (CLAUDE.md) : les autres apps (ex. ``apps.pos`` à
l'écran caisse) lisent l'état fidélité à travers ces fonctions plutôt qu'en
important ``apps.fidelite.models`` directement.
"""


def programme_actif(company):
    """Le ``ProgrammeFidelite`` ACTIF de la société, ou None. Lecture seule."""
    from .models import ProgrammeFidelite
    return ProgrammeFidelite.objects.filter(company=company, actif=True).first()


def get_compte(company, client_id):
    """``CompteFidelite`` scopé société par id client, ou None. Lecture seule."""
    from .models import CompteFidelite
    if not client_id:
        return None
    return CompteFidelite.objects.filter(
        company=company, client_id=client_id).first()
