"""Lectures cross-app du domaine « Paramètres / Société ».

Point d'entrée UNIQUE pour les autres apps (ventes, crm, …) qui ont besoin de
l'identité société ou des repères tarifaires : elles passent par ces fonctions
plutôt que d'importer ``CompanyProfile`` directement, ce qui garde une seule
source de vérité et respecte la frontière cross-app.

Tout est en lecture seule. Aucun de ces accès n'écrit ni ne fabrique de valeur :
on lit le profil de la société (ou le profil pk=1 par défaut) et on renvoie ses
champs tels quels, avec un repli explicite quand le profil est absent.
"""
from __future__ import annotations

from decimal import Decimal


def _profile(company):
    """Profil société (ou pk=1 par défaut). Repli None si la table n'existe pas."""
    def _load():
        try:
            from apps.parametres.models import CompanyProfile
            return CompanyProfile.get(company=company)
        except Exception:  # noqa: BLE001 — un PDF/simulateur ne casse jamais ici
            return None

    # SCA43 / NTPLT16 — mémo PAR REQUÊTE (contextvar), MÊME clé que
    # ``ventes.utils.company_settings._profile`` : les deux accesseurs lisent le
    # MÊME ``CompanyProfile`` de la société, donc ils partagent un seul objet
    # mémorisé le temps d'une requête. Hors requête → cache inactif (inchangé).
    from core import request_cache
    return request_cache.memoize(
        ("parametres.company_profile", getattr(company, "id", None)), _load)


def company_identity(company) -> dict:
    """Identité légale + coordonnées d'une société pour les documents (devis/PDF).

    Renvoie un dict sérialisable JSON. Toutes les valeurs sont des chaînes
    (vides quand non renseignées) sauf ``couleur_principale`` qui porte le
    hex de la charte. Aucune valeur codée en dur d'un tenant particulier :
    quand aucun profil n'existe, tous les champs texte sont vides et le moteur
    PDF applique ses littéraux historiques par défaut.
    """
    p = _profile(company)
    if p is None:
        return {
            "nom": "", "adresse": "", "email": "", "telephone": "",
            "ice": "", "identifiant_fiscal": "", "rc": "", "patente": "",
            "cnss": "", "rib": "", "banque": "", "couleur_principale": "",
            "site_web": "",
        }
    return {
        "nom": p.nom or "",
        "adresse": p.adresse or "",
        "email": p.email or "",
        "telephone": p.telephone or "",
        "ice": p.ice or "",
        "identifiant_fiscal": p.identifiant_fiscal or "",
        "rc": p.rc or "",
        "patente": p.patente or "",
        "cnss": p.cnss or "",
        "rib": p.rib or "",
        "banque": p.banque or "",
        "couleur_principale": p.couleur_principale or "",
        # SCA27 — site web (pilote la ligne site + la base des liens fiches du
        # PDF résidentiel). Vide → littéraux historiques (taqinor.ma).
        "site_web": getattr(p, "site_web", "") or "",
    }


def tariff_for(company) -> dict:
    """Repères ROI/tarifaires CANONIQUES d'une société (source unique — DC5).

    CompanyProfile est la source de vérité déjà consommée ; tout lecteur (moteur
    de devis, simulateur) passe par ici plutôt que de dupliquer les constantes.
    Repli sur les défauts historiques du simulateur (1.75 MAD/kWh, 1600 kWh/kWc,
    rendement 0.8, TVA 20/10) quand aucun profil n'existe.
    """
    p = _profile(company)
    if p is None:
        return {
            "onee_tarif_kwh": 1.75,
            "productible_kwh_kwc": 1600.0,
            "rendement_global": 0.8,
            "tva_standard": 20.0,
            "tva_panneaux": 10.0,
        }

    def _f(val, default):
        try:
            return float(val)
        except (TypeError, ValueError):
            return float(default)

    return {
        "onee_tarif_kwh": _f(p.onee_tarif_kwh, Decimal("1.75")),
        "productible_kwh_kwc": _f(p.productible_kwh_kwc, Decimal("1600.0")),
        "rendement_global": _f(p.rendement_global, Decimal("0.8")),
        "tva_standard": _f(p.tva_standard, Decimal("20")),
        "tva_panneaux": _f(p.tva_panneaux, Decimal("10")),
    }
