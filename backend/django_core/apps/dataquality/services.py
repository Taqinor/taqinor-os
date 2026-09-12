"""NTDATA14 — évaluation des règles de qualité sur une population de lignes.

Fonctions PURES au-dessus de ``core.rules`` : elles prennent des dicts (les
lignes que ``core.data_explorer.run_query`` rend déjà) et disent lesquelles
sont EN VIOLATION. Aucun import d'app métier, aucune écriture.

POURQUOI UNE COUCHE AU-DESSUS DE ``core.rules``. Deux types de règles n'y sont
pas exprimables et c'est assumé, pas contourné :

* ``format`` — ``core.rules`` n'a aucun opérateur d'expression régulière
  (ses opérateurs de feuille sont ``eq/ne/gt/gte/lt/lte/in/not_in/contains/
  startswith/exists``). Y ajouter une regex serait ouvrir un évaluateur non
  borné dans la couche fondation ; on compile donc le motif ici, une fois par
  règle.
* ``unicite`` — la conformité d'une ligne dépend des AUTRES lignes. Aucun
  moteur ligne-par-ligne ne peut répondre.

``non_vide`` et ``plage`` passent, eux, PAR ``core.rules``
(``evaluate_condition_group``) — jamais une seconde implémentation.

UNE VALEUR VIDE N'EST PAS UNE VIOLATION, sauf pour ``non_vide``. Un ICE absent
est un trou de COMPLÉTUDE (NTDATA16), pas un format faux : dire « format
invalide » d'une case vide gonflerait artificiellement le taux de non-conformité
et ferait chercher une faute qui n'existe pas.
"""
from __future__ import annotations

import re

from .models import RegleQualite


def _est_vide(valeur):
    """Vrai pour ``None`` et pour une chaîne blanche — jamais pour 0/False.

    Zéro et « faux » sont des valeurs RENSEIGNÉES : les compter comme vides
    ferait passer un stock à 0 ou une case décochée pour une donnée manquante.
    """
    if valeur is None:
        return True
    if isinstance(valeur, str):
        return not valeur.strip()
    return False


def _viole_format(regle, valeur):
    motif = (regle.parametres or {}).get('motif')
    if not motif:
        return False
    try:
        compile_ = re.compile(motif)
    except re.error:
        # Motif devenu invalide après coup : on ne juge RIEN plutôt que de
        # déclarer toute la population fautive.
        return False
    return compile_.match(str(valeur)) is None


def _viole_reference(regle, valeur):
    valeurs = (regle.parametres or {}).get('valeurs') or []
    return valeur not in valeurs


def _viole_core_rules(regle, ligne):
    """``non_vide`` / ``plage`` — délégué à ``core.rules`` (jamais réécrit)."""
    from core.rules import evaluate_condition_group

    condition = regle.condition_core_rules
    if condition is None:
        return False
    if not condition.get('conditions') and 'op' in condition:
        # Groupe VIDE (une règle « plage » sans borne ne devrait pas exister,
        # la validation du modèle l'interdit) : rien à juger.
        return False
    conforme = evaluate_condition_group(condition, dict(ligne))
    return not conforme


def ligne_en_violation(regle, ligne):
    """Cette ligne viole-t-elle ``regle`` ? (règles LIGNE À LIGNE uniquement)

    ``unicite`` renvoie toujours ``False`` ici : elle se juge sur la
    population (voir :func:`violations`).
    """
    valeur = ligne.get(regle.champ)
    if regle.type_regle == RegleQualite.TypeRegle.NON_VIDE:
        # `exists` de core.rules teste la PRÉSENCE de la clé ; une chaîne
        # blanche est présente mais vide. On écarte donc le cas vide ici, et
        # on laisse core.rules juger la présence.
        if _est_vide(valeur):
            return True
        return _viole_core_rules(regle, ligne)
    if _est_vide(valeur):
        # Trou de complétude, pas une faute de format/plage/référentiel.
        return False
    if regle.type_regle == RegleQualite.TypeRegle.FORMAT:
        return _viole_format(regle, valeur)
    if regle.type_regle == RegleQualite.TypeRegle.REFERENCE_VALIDE:
        return _viole_reference(regle, valeur)
    if regle.type_regle == RegleQualite.TypeRegle.PLAGE:
        return _viole_core_rules(regle, ligne)
    return False


def violations(regle, lignes, *, cle_id='id'):
    """Les identifiants des lignes en violation de ``regle``.

    ``lignes`` — itérable de dicts (le rendu de ``data_explorer.run_query``).
    Renvoie ``(nb_lignes, identifiants_en_violation)``, les identifiants dans
    l'ordre de lecture (déterministe).
    """
    lignes = list(lignes)
    if regle.type_regle == RegleQualite.TypeRegle.UNICITE:
        vues = {}
        fautives = []
        for ligne in lignes:
            valeur = ligne.get(regle.champ)
            if _est_vide(valeur):
                continue  # une case vide n'est jamais un doublon
            cle = str(valeur).strip().lower()
            if cle in vues:
                # La PREMIÈRE occurrence compte aussi : un doublon est un
                # groupe, pas une ligne isolée.
                if vues[cle] is not None:
                    fautives.append(vues[cle])
                    vues[cle] = None
                fautives.append(ligne.get(cle_id))
            else:
                vues[cle] = ligne.get(cle_id)
        return len(lignes), fautives
    fautives = [ligne.get(cle_id) for ligne in lignes
                if ligne_en_violation(regle, ligne)]
    return len(lignes), fautives


def taux_conformite(nb_lignes, nb_violations):
    """Part conforme, en pourcentage arrondi au dixième.

    Population VIDE ⇒ ``None``, jamais 100 % : « aucune donnée » n'est pas
    « tout est bon » — afficher 100 % sur zéro ligne serait un chiffre faux.
    """
    if not nb_lignes:
        return None
    conformes = max(0, nb_lignes - nb_violations)
    return round(conformes / nb_lignes * 100, 1)
