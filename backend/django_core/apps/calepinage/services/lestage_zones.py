"""ACAL563 — les zones de POSE du toit plat (rive, coin) du ``lestage``.

Quatre paramètres, chacun ``{'valeur', 'source'}``, vides par défaut :
largeur de la bande de rive, largeur de coin, lest additionnel en rive et en
coin. Ils ne peuvent pas entrer dans ``PARAMETRES`` (la feuille les listerait
« manquants » dans la feuille d'aujourd'hui) : ils vivent sous la clé de
structure ``zones_de_pose``. Aucune valeur n'est écrite ici : tout se saisit
avec sa source (CALX361).
"""
from __future__ import annotations

from .parametres import ReglageInvalide

CLE_ZONES_DE_POSE = 'zones_de_pose'

#: clé → (libellé, strictement positif ?). Une largeur est > 0, un lest >= 0.
PARAMETRES_ZONES_DE_POSE = {
    'largeur_bande_rive_m': ("Largeur de la bande de rive (m)", True),
    'largeur_coin_m': ("Largeur de coin (m)", True),
    'lest_rive_kg_par_module': (
        "Lest additionnel en rive (kg par module)", False),
    'lest_coin_kg_par_module': (
        "Lest additionnel en coin (kg par module)", False),
}


def _refus(message, champ):
    return ReglageInvalide(message, champ=champ)


def normaliser_zones_de_pose(valeur):
    """``zones_de_pose`` VALIDÉE — ``{}`` si rien n'est saisi.

    Raises:
        ReglageInvalide: message français nommant ``zones_de_pose.<clé>``.
    """
    if valeur is None or valeur == {}:
        return {}
    if not isinstance(valeur, dict):
        raise _refus(
            "Les zones de pose se saisissent en objet "
            f"(reçu : {type(valeur).__name__}).", CLE_ZONES_DE_POSE)
    inconnues = sorted(set(valeur) - set(PARAMETRES_ZONES_DE_POSE))
    if inconnues:
        raise _refus(
            f"Zones de pose : clé inconnue « {inconnues[0]} ». Admises : "
            f"{', '.join(PARAMETRES_ZONES_DE_POSE)}.",
            f'{CLE_ZONES_DE_POSE}.{inconnues[0]}')
    propre = {}
    for cle, brut in valeur.items():
        if brut is None:
            continue
        libelle, strict = PARAMETRES_ZONES_DE_POSE[cle]
        champ = f'{CLE_ZONES_DE_POSE}.{cle}'
        if not isinstance(brut, dict):
            raise _refus(
                f"« {libelle} » se saisit avec sa source : "
                '{"valeur": …, "source": "référence du texte"}.', champ)
        surplus = sorted(set(brut) - {'valeur', 'source'})
        if surplus:
            raise _refus(
                f"« {libelle} » n'accepte que « valeur » et « source » "
                f"(reçu en plus : {', '.join(surplus)}).", champ)
        source = brut.get('source')
        if not isinstance(source, str) or not source.strip():
            raise _refus(
                f"« {libelle} » doit porter la RÉFÉRENCE du texte d'où elle "
                "vient : aucune valeur n'est admise sans sa source.", champ)
        nombre = brut.get('valeur')
        if isinstance(nombre, bool) or not isinstance(nombre, (int, float)):
            raise _refus(
                f"« {libelle} » doit être un nombre "
                f"(reçu : {type(nombre).__name__}).", champ)
        if float(nombre) < 0 or (strict and float(nombre) == 0):
            raise _refus(
                f"« {libelle} » doit être "
                + ("supérieure à zéro" if strict else "positif ou nul")
                + f" (reçu : {nombre}).", champ)
        propre[cle] = {'valeur': float(nombre), 'source': source.strip()}
    return propre
