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
        company=company, client_id=client_id).select_related('palier_actuel').first()


def palier_et_remise_pour_client(company, client_id):
    """NTRET10 — lecture seule : palier actuel + remise % applicable pour un
    client, DESTINÉE aux autres apps (ex. ``apps.pos`` à l'écran caisse) qui
    veulent afficher/appliquer la remise palier SANS importer
    ``apps.fidelite.models``. Ne lève jamais — renvoie des valeurs vides si
    aucun compte/palier."""
    compte = get_compte(company, client_id)
    if compte is None or compte.palier_actuel_id is None:
        return {'palier': None, 'remise_pct': None, 'points_bonus_pct': None}
    palier = compte.palier_actuel
    return {
        'palier': palier.libelle,
        'remise_pct': palier.remise_pct,
        'points_bonus_pct': palier.points_bonus_pct,
    }
