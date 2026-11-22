"""ACAL749 — ce que cette simulation ne modélise PAS (``cascade.limites_connues``).

Les étapes OMISES sont déjà dites par la cascade, avec leur motif : cette
liste-ci nomme ce qui n'entre dans AUCUNE étape. Texte sans chiffre, constante
de code ; chaque limite est vérifiée contre le code par
``tests/test_calx141_contrat_cascade.py``. Référence : IEA PVPS Task 13,
incertitudes des études de productible
(https://iea-pvps.org/wp-content/uploads/2020/01/Uncertainties_in_PV_System_Yield_Predictions_and_Assessments_by_Task_13.pdf).
"""
from __future__ import annotations

__all__ = ['HORS_MODELE', 'LIMITE_OMBRAGE_DIFFUS', 'limites_connues']

#: Toujours vraies aujourd'hui (le test les affirme une à une contre le code).
HORS_MODELE = (
    {'code': 'pas_horaire',
     'texte_fr': "La simulation travaille à l'heure : un passage nuageux de "
                 "quelques minutes n'est pas vu, et le pas du quart d'heure "
                 "est refusé à l'export.",
     'texte_en': 'The simulation runs hourly: a cloud passing for a few '
                 'minutes is not seen, and the quarter-hour step is refused '
                 'on export.'},
    {'code': 'suiveurs',
     'texte_fr': "Toute pose est fixe : aucun suiveur solaire n'est modélisé.",
     'texte_en': 'Every mounting is fixed: no solar tracker is modelled.'},
    {'code': 'courbe_iv',
     'texte_fr': 'Le panneau suit les coefficients de sa fiche, pas une '
                 'courbe courant-tension cellule par cellule.',
     'texte_en': 'The module follows its datasheet coefficients, not a '
                 'cell-by-cell current-voltage curve.'},
    {'code': 'charges_structure',
     'texte_fr': 'Vent et neige sur la structure : saisis par la société, '
                 "aucune valeur n'est tirée d'une norme.",
     'texte_en': 'Wind and snow on the structure: entered by the company, '
                 'no value is taken from a standard.'},
)

#: Servie SEULEMENT si l'étape ``ombrage_diffus`` manque à ``ORDRE_ETAPES``.
LIMITE_OMBRAGE_DIFFUS = {
    'code': 'ombrage_diffus',
    'texte_fr': "L'ombre sur la lumière diffuse n'est pas retirée.",
    'texte_en': 'Shading of diffuse light is not removed.'}


def limites_connues(ordre_etapes):
    """La liste servie, copiée (jamais la constante elle-même)."""
    limites = [dict(limite) for limite in HORS_MODELE]
    if 'ombrage_diffus' not in tuple(ordre_etapes or ()):
        limites.append(dict(LIMITE_OMBRAGE_DIFFUS))
    return limites
