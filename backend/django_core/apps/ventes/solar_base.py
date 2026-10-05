"""SPL259 — helpers FEUILLES du moteur solaire (déplacés de ``solar_design.py``).

Hypothèses et omissions PUBLIÉES (CALX286) et lecture tolérante d'une série :
``solar_design`` et ``solar_finance`` les importent POUR USAGE. Module pur :
bibliothèque standard seulement, aucune dépendance interne (feuille) — il
n'importe jamais ``solar_design`` en retour.

Déplacement « move only » : corps, docstrings et littéraux sont
OCTET-IDENTIQUES (``_source_defaut`` publie toujours le chemin d'origine
``apps/ventes/solar_design.py``, lu par ``test_calx286_non_invention``) —
prouvé par ``tests/test_split_devis_solar.py`` (golden ``split_sd_base``).
"""
from __future__ import annotations


# ── CALX286 — hypothèses et omissions PUBLIÉES (jamais un défaut muet) ───────
# Toute grandeur qui dépend d'un défaut NON SOURCÉ non fourni par l'appelant
# sort ``None`` avec une entrée ``omissions`` ; tout défaut qui reste appliqué
# (hors des familles retirées par CALX286) est publié dans ``hypotheses`` avec
# sa provenance. ``couvre`` liste les clés de sortie (chemins pointés) que
# l'entrée gouverne — le test de non-invention s'appuie dessus.

def _source_defaut(nom):
    """Provenance d'un défaut codé du module : son NOM, et le fait qu'il n'est
    pas sourcé."""
    return (f"défaut codé du module (apps/ventes/solar_design.py {nom}) — "
            "valeur non sourcée, appliquée faute de saisie")


def _hypothese(cle, valeur, source, couvre=None):
    """Une hypothèse appliquée, avec sa source et les sorties qu'elle gouverne."""
    return {"cle": cle, "valeur": valeur, "source": source,
            "couvre": list(couvre or [cle])}


def _omission(cle, motif, couvre=None):
    """Une grandeur omise faute de saisie, avec son motif et ses dépendantes."""
    return {"cle": cle, "motif": motif, "couvre": list(couvre or [cle])}


def _taux_ou_none(valeur):
    """Nombre lu dans ``valeur``, ou ``None`` s'il est absent/illisible/NaN."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _omissions_temperatures(cold_temp_c, hot_temp_c, couvre):
    """Omissions des températures de dimensionnement non fournies."""
    omissions = []
    for cle, valeur, libelle in (("cold_temp_c", cold_temp_c, "minimale"),
                                 ("hot_temp_c", hot_temp_c, "maximale")):
        if _taux_ou_none(valeur) is None:
            omissions.append(_omission(
                cle,
                f"omis : température cellule {libelle} de dimensionnement non "
                f"fournie ({cle}) — la fenêtre de tension en dépend, aucune "
                "température n'est supposée",
                couvre))
    return omissions


def _coerce_series(values):
    """Convertit un itérable en liste de floats ≥ 0 (illisible/<0 → 0.0).

    Préserve la longueur : chaque case impossible à lire ou négative devient
    0.0 (jamais de rejet, jamais d'exception). ``None`` → liste vide.
    """
    if values is None:
        return []
    out = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.0
        if f < 0.0 or f != f:  # négatif ou NaN → 0
            f = 0.0
        out.append(f)
    return out
