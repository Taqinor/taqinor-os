"""Sélecteurs LECTURE SEULE du module Gestion de flotte.

Point d'entrée des LECTURES cross-app vers la flotte. Les autres apps ne lisent
jamais les modèles flotte directement : elles passent par ces fonctions, toutes
scopées par société (CLAUDE.md, règle de modularité cross-app).
"""
from .models import ActifFlotte, EnginRoulant, Vehicule


def vehicules_de_la_societe(company):
    """Tous les véhicules d'une société (queryset scopé)."""
    return Vehicule.objects.filter(company=company)


def engins_de_la_societe(company):
    """Tous les engins roulants d'une société (queryset scopé)."""
    return EnginRoulant.objects.filter(company=company)


def actifs_de_la_societe(company):
    """FLOTTE5 — Tous les actifs unifiés d'une société (queryset scopé).

    Sélecteur cross-app : les futurs modules entretien/sinistre/document
    appellent cette fonction plutôt que d'importer directement ``ActifFlotte``.
    """
    return ActifFlotte.objects.filter(company=company).select_related(
        'vehicule', 'engin')


def actif_par_vehicule(company, vehicule_id):
    """FLOTTE5 — Retourne l'``ActifFlotte`` associé à un véhicule donné,
    ou ``None`` s'il n'existe pas encore."""
    return ActifFlotte.objects.filter(
        company=company, vehicule_id=vehicule_id).first()


def actif_par_engin(company, engin_id):
    """FLOTTE5 — Retourne l'``ActifFlotte`` associé à un engin donné,
    ou ``None`` s'il n'existe pas encore."""
    return ActifFlotte.objects.filter(
        company=company, engin_id=engin_id).first()


def emplacement_stock_label(company, emplacement_stock_id):
    """FLOTTE3 — Libellé de l'emplacement de stock lié à un véhicule.

    Résout `emplacement_stock_id` via le sélecteur LECTURE de `apps.stock`
    (import local, jamais `apps.stock.models`). Renvoie le nom de
    l'``EmplacementStock`` s'il existe et appartient à la SOCIÉTÉ, sinon dégrade
    sur l'id nu (``"#<id>"``) ; ``None`` si aucun lien. Lecture seule.
    """
    if not emplacement_stock_id:
        return None
    try:
        from apps.stock import selectors as stock_selectors
        emplacement = stock_selectors.get_emplacement_scoped(
            company, emplacement_stock_id)
    except Exception:
        emplacement = None
    if emplacement is not None:
        return str(emplacement)
    return f'#{emplacement_stock_id}'
