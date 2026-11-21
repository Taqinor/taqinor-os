"""ACAL630 — importer un plan de chaînes CSV (``module;chaine;mppt;onduleur``).

Un plan tiré d'un autre logiciel arrive en tableau : le CSV n'est qu'une
autre ENTRÉE de l'affectation manuelle. ``lire_csv_affectation`` valide
LUI-MÊME chaque ligne et rend un refus par défaut trouvé, chacun nommant SA
ligne de fichier (l'en-tête est la ligne 1) et sa colonne — là où
``normaliser_affectation_imposee`` s'arrête à la première erreur sans ligne
ni colonne. Seules les lignes sans refus passent ensuite au verdict
d'affectation existant (``services/chaines.py``, non modifié).

Rien n'est écrit : ``applique`` vaut toujours ``False`` ; l'utilisateur valide
en enregistrant l'entrée électrique (``affectation_manuelle``). Forme du
contrat ``contract_samples/calepinage_import_affectation.json`` (ACAL629).
"""
from __future__ import annotations

__all__ = ['COLONNES', 'importer_affectation', 'lire_csv_affectation']

COLONNES = ('module', 'chaine', 'mppt', 'onduleur')
SEPARATEUR = ';'
ENTETE = SEPARATEUR.join(COLONNES)

#: Le sujet de chaque colonne numérique, tel que le message le nomme.
SUJETS = {'chaine': 'La chaîne', 'mppt': "L'entrée MPPT",
          'onduleur': "L'onduleur"}


def _refus(ligne, colonne, message):
    return {'ligne': ligne, 'colonne': colonne, 'message': message}


def _entier(texte):
    """Un entier strictement positif, ``None`` (cellule vide), ou ``False``."""
    if texte == '':
        return None
    if texte.isascii() and texte.isdigit() and int(texte) > 0:
        return int(texte)
    return False


def _entete(premiere):
    """``(colonnes, refus)`` — l'en-tête lu, ou le refus de la ligne 1."""
    colonnes = [cellule.strip().lower() for cellule in premiere.split(
        SEPARATEUR)]
    inconnues = [c for c in colonnes if c not in COLONNES]
    if inconnues:
        return None, _refus(1, inconnues[0], "Colonne inconnue « %s » : "
                            "en-tête attendu %s" % (inconnues[0], ENTETE))
    manquantes = [c for c in COLONNES if c not in colonnes]
    if manquantes or len(set(colonnes)) != len(colonnes):
        return None, _refus(1, None, "En-tête attendu : %s" % ENTETE)
    return colonnes, None


def lire_csv_affectation(texte):
    """``(lignes, refus)`` — les lignes valides et un refus par défaut."""
    lignes_fichier = str(texte or '').splitlines()
    if not lignes_fichier or not lignes_fichier[0].strip():
        return [], [_refus(1, None, "En-tête attendu : %s" % ENTETE)]
    colonnes, refus_entete = _entete(lignes_fichier[0])
    if refus_entete:
        return [], [refus_entete]
    lignes, refus, vus = [], [], set()
    for numero, brute in enumerate(lignes_fichier[1:], start=2):
        if not brute.strip():
            continue
        cellules = [cellule.strip() for cellule in brute.split(SEPARATEUR)]
        if len(cellules) != len(colonnes):
            refus.append(_refus(numero, None, "La ligne compte %d colonnes "
                                "pour %d attendues (%s)."
                                % (len(cellules), len(colonnes), ENTETE)))
            continue
        valeurs = dict(zip(colonnes, cellules))
        fautes = []
        if not valeurs['module']:
            fautes.append(_refus(numero, 'module',
                                 "Le module n'est pas nommé."))
        elif valeurs['module'] in vus:
            fautes.append(_refus(numero, 'module', "Le module « %s » est "
                                 "déjà affecté plus haut dans le fichier."
                                 % valeurs['module']))
        ligne = {'module': valeurs['module']}
        for colonne in COLONNES[1:]:
            entier = _entier(valeurs[colonne])
            if entier is False:
                fautes.append(_refus(numero, colonne, "%s doit être un entier "
                                     "strictement positif (reçu : %s)"
                                     % (SUJETS[colonne], valeurs[colonne])))
            ligne[colonne] = entier
        if fautes:
            refus.extend(fautes)
            continue
        vus.add(ligne['module'])
        lignes.append(ligne)
    return lignes, refus


def importer_affectation(calepinage, texte):
    """``{lignes, refus, bloquants, applique: False}`` — rien n'est écrit."""
    from .chaines import (
        AffectationInvalide, normaliser_affectation_imposee,
        verdict_affectation,
    )
    from .electrique import conception_du_calepinage

    lignes, refus = lire_csv_affectation(texte)
    bloquants = []
    if lignes:
        conception, materiel, _donnees, _doc = conception_du_calepinage(
            calepinage)
        if conception.fiche_incomplete:
            bloquants = ["Verdict d'affectation non calculable : %s" % manque
                         for manque in conception.manquantes]
        else:
            try:
                bloquants = list(verdict_affectation(
                    conception, normaliser_affectation_imposee(lignes),
                    specs_onduleur=materiel.get('onduleur')))
            except AffectationInvalide as erreur:
                bloquants = [str(erreur)]
    return {'lignes': lignes, 'refus': refus, 'bloquants': bloquants,
            'applique': False}
