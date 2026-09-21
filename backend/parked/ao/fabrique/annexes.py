"""AOF142 — annexe de fiches techniques : une fiche par équipement ACTIF.

L'oubli statistiquement le plus fréquent
=======================================
Quand un équipement bascule, trois choses doivent bouger ensemble : la
désignation, le prix… et la FICHE TECHNIQUE annexée. La troisième est celle
qu'on oublie. Le dossier part alors avec la fiche du matériel qu'on ne fournit
plus — un écart que le maître d'ouvrage voit immédiatement et qui décrédibilise
tout le reste du mémoire.

Ce module rend l'oubli impossible en le rendant MÉCANIQUE :

* ``index_annexes``      — l'index est GÉNÉRÉ depuis les équipements actifs,
                           jamais rédigé ; une fiche ajoutée s'y numérote
                           toute seule ;
* ``fiches_orphelines``  — fiches dont l'équipement n'est plus actif ;
* ``fiches_manquantes``  — équipements actifs sans fiche ;
* ``appliquer_bascule``  — retire la fiche de l'ancien ET ajoute celle du
                           nouveau, en une seule opération (les deux moitiés
                           séparées sont exactement la façon dont on garde une
                           fiche périmée).

Module PUR : listes de dicts, aucun ORM, aucune I/O.

Contrat d'entrée
----------------
``equipements`` : ``[{'reference', 'designation', 'role', 'actif'}]``
``fiches``      : ``[{'reference_equipement', 'titre', 'pages', 'empreinte'}]``
"""
from __future__ import annotations

__all__ = [
    'ORDRE_ROLES',
    'index_annexes',
    'fiches_orphelines',
    'fiches_manquantes',
    'appliquer_bascule',
    'controler_annexes',
]

#: Ordre de présentation des fiches : du plus structurant au plus périphérique.
#: Un rôle inconnu passe en fin, sans faire échouer l'index — l'index n'est pas
#: le bon endroit pour refuser un matériel.
ORDRE_ROLES = (
    'module', 'onduleur', 'batterie', 'ems', 'coffret_dc', 'coffret_ac',
    'tgpv', 'cable', 'structure', 'station_meteo', 'afficheur', 'variateur',
)


def _actifs(equipements):
    return [equipement for equipement in (equipements or [])
            if equipement.get('actif', True)]


def _rang(role):
    role = str(role or '')
    return ORDRE_ROLES.index(role) if role in ORDRE_ROLES else len(ORDRE_ROLES)


def index_annexes(equipements, fiches):
    """Index NUMÉROTÉ des fiches annexées, dérivé des équipements actifs.

    Renvoie ``[{'numero', 'reference', 'designation', 'role', 'titre',
    'pages', 'presente'}]``. Une fiche manquante apparaît avec
    ``presente=False`` plutôt que d'être omise : un trou visible vaut mieux
    qu'un index court qui a l'air complet.
    """
    par_reference = {str(fiche.get('reference_equipement')): fiche
                     for fiche in (fiches or [])}
    lignes = []
    actifs = sorted(
        _actifs(equipements),
        key=lambda e: (_rang(e.get('role')), str(e.get('reference') or '')),
    )
    for numero, equipement in enumerate(actifs, start=1):
        reference = str(equipement.get('reference') or '')
        fiche = par_reference.get(reference)
        lignes.append({
            'numero': numero,
            'reference': reference,
            'designation': equipement.get('designation') or '',
            'role': equipement.get('role') or '',
            'titre': (fiche or {}).get('titre') or '',
            'pages': (fiche or {}).get('pages'),
            'presente': fiche is not None,
        })
    return lignes


def fiches_orphelines(equipements, fiches):
    """Fiches annexées dont l'équipement n'est plus actif (ou n'existe pas)."""
    references_actives = {str(equipement.get('reference') or '')
                          for equipement in _actifs(equipements)}
    return [fiche for fiche in (fiches or [])
            if str(fiche.get('reference_equipement')) not in references_actives]


def fiches_manquantes(equipements, fiches):
    """Équipements actifs sans fiche technique annexée."""
    references_fiches = {str(fiche.get('reference_equipement'))
                         for fiche in (fiches or [])}
    return [equipement for equipement in _actifs(equipements)
            if str(equipement.get('reference') or '') not in references_fiches]


def appliquer_bascule(fiches, *, ancienne_reference, nouvelle_fiche=None):
    """Retire la fiche de l'ancien équipement ET ajoute celle du nouveau.

    Les deux moitiés dans le MÊME appel : c'est la séparation des deux gestes
    qui produit le dossier portant deux fiches contradictoires. Renvoie une
    NOUVELLE liste (les entrées d'origine ne sont pas mutées).
    """
    ancienne = str(ancienne_reference or '')
    restantes = [dict(fiche) for fiche in (fiches or [])
                 if str(fiche.get('reference_equipement')) != ancienne]
    if nouvelle_fiche:
        reference = str(nouvelle_fiche.get('reference_equipement') or '')
        if not reference:
            raise ValueError(
                "La fiche à annexer ne cite aucun équipement : elle serait "
                "orpheline dès son ajout.")
        restantes = [fiche for fiche in restantes
                     if str(fiche.get('reference_equipement')) != reference]
        restantes.append(dict(nouvelle_fiche))
    return restantes


def controler_annexes(equipements, fiches):
    """Verdict d'annexe : orphelines + manquantes + index généré.

    ``bloquant`` est vrai dès qu'une fiche orpheline subsiste : une fiche
    périmée dans un pli déposé est irrattrapable, alors qu'une fiche manquante
    se voit et se réclame.
    """
    orphelines = fiches_orphelines(equipements, fiches)
    manquantes = fiches_manquantes(equipements, fiches)
    return {
        'index': index_annexes(equipements, fiches),
        'orphelines': orphelines,
        'manquantes': manquantes,
        'bloquant': bool(orphelines),
        'avertissements': [
            "Équipement actif sans fiche technique : {} ({})".format(
                equipement.get('designation') or '',
                equipement.get('reference') or '')
            for equipement in manquantes
        ],
    }
