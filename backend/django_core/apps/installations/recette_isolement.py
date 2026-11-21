"""ACAL670 — l'essai d'isolement de la recette jugé contre le seuil SOCIÉTÉ.

Le seuil est le réglage ``recette_isolement_min_mohm`` (ACAL669), saisi par
la société, jamais une constante. Sans seuil ou sans mesure, aucun verdict
n'est inventé : ``isolement_ok`` reste ce que la personne a saisi.
"""
from decimal import Decimal, InvalidOperation


def seuil_isolement_mohm(company):
    """La résistance d'isolement minimale (MΩ) saisie par la société, ou
    ``None`` (même lecture que ``services.seuil_ecart_pmax``)."""
    from .services import _reglage_recette
    return _reglage_recette(company, 'recette_isolement_min_mohm')


def juger_isolement(mesure_mohm, seuil_mohm, saisi):
    """``isolement_ok`` : jugé par le serveur quand mesure ET seuil sont
    connus (mesure ≥ seuil), sinon la valeur saisie, inchangée."""
    if mesure_mohm is None or seuil_mohm is None:
        return saisi
    try:
        return Decimal(str(mesure_mohm)) >= Decimal(str(seuil_mohm))
    except (InvalidOperation, ValueError):
        return saisi
