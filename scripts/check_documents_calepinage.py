#!/usr/bin/env python3
"""Garde CI (CALX329) : un document DÉCLARÉ dans une liste de pièces du
module calepinage doit avoir un RENDU — ou un motif EXPLICITEMENT marqué
« produit ailleurs ».

POURQUOI CETTE GARDE EXISTE — LE DÉFAUT DE CALX309
----------------------------------------------------
``SPEC_PIECES`` (``apps/calepinage/services/pack_technique.py``) déclarait
QUATRE pièces ; ``_rendus`` n'en mappait que DEUX. RIEN ne comparait les
deux listes : le dossier technique sortait toujours amputé, et la seule
conséquence visible était une phrase de signalement noyée dans la réponse
JSON (``pack_technique.py:126`` avant correction) — personne ne l'a vue
avant le fondateur, en ouvrant l'écran. Le même écart peut survenir demain
dans ``reglementaire.PIECES_PRODUITES`` ou dans l'inventaire ``documents``
du lot 6 (``services/documents/__init__.py``, CALX321) : CETTE garde le
détecte AVANT que quiconque le découvre à la main.

CE QU'ELLE VÉRIFIE (analyse STATIQUE, stdlib ``ast``, sans Django, sans DB)
----------------------------------------------------------------------------
Pour chacune des trois paires (liste déclarative de pièces, dictionnaire de
rendus) du module :

1. ``pack_technique.SPEC_PIECES``               <-> les clés que
   ``pack_technique._rendus()`` retourne ;
2. ``reglementaire.PIECES_PRODUITES``            <-> les clés que
   ``reglementaire._rendus_du_module()`` retourne ;
3. ``documents.__init__._DEFINITIONS_DOCUMENTS`` <-> les clés du registre
   partagé ``documents.__init__.MISES_EN_PAGE`` (CALX323 — le dictionnaire
   initial PLUS chaque ligne ``MISES_EN_PAGE['code'] = ...`` ajoutée par une
   tâche suivante du lot).

... elle affirme :

* chaque code DÉCLARÉ a une entrée de rendu, OU figure dans
  ``PRODUIT_AILLEURS`` avec un motif VÉRIFIÉ et non vide ;
* aucune clé de rendu n'est ORPHELINE — un code qui a un rendu mais n'est
  déclaré NULLE PART est du code mort qui se croit vivant, la même famille
  de défaut que ``check_ecrans_atteignables.py`` (incident du 03/08/2026) ;
* chaque entrée de ``PRODUIT_AILLEURS`` correspond ENCORE à un code
  RÉELLEMENT déclaré — une exemption devenue orpheline (le code a été
  retiré, ou a fini par obtenir un vrai rendu) est un filtre mort et cette
  garde le NOMME plutôt que de le laisser protéger dans le vide.

RATCHET NON ÉPINGLÉ : la garde COMPTE les écarts trouvés, elle ne fige
AUCUN total — un document neuf déclaré EN MÊME TEMPS que son rendu ne casse
jamais cette garde ; seul un écart entre les deux la fait rougir.

``MISES_EN_PAGE`` ne couvre QUE les pièces qui partagent une mise en page
HTML unique entre le PDF et l'aperçu (CALX323) : quatre codes de
l'inventaire ``documents`` en sont légitimement absents aujourd'hui
(``export_projet_json`` — format JSON, pas de HTML ; ``diagramme_pertes`` —
image SVG servie par un endpoint dédié ; ``dossier_fin_chantier`` — fusion
d'octets de plusieurs pièces, pas une mise en page unique ;
``rapport_ombrage`` — a bien SON PROPRE rendu et SON PROPRE endpoint HTTP,
simplement pas encore branché sur le registre partagé). Chacun est déclaré
dans ``PRODUIT_AILLEURS['documents']`` avec le motif VÉRIFIÉ sur le dépôt
(voir son endpoint réel dans ``apps/calepinage/views/documents.py``), jamais
deviné.

Run :
    python scripts/check_documents_calepinage.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CALEPINAGE = REPO_ROOT / 'backend' / 'django_core' / 'apps' / 'calepinage'

#: Codes DÉCLARÉS dans l'inventaire ``documents`` dont le rendu vit AILLEURS
#: que dans ``MISES_EN_PAGE`` — chacun avec un motif VÉRIFIÉ sur le dépôt
#: réel, jamais un silence. ``test_chaque_exemption_correspond_a_un_code_
#: reellement_declare`` (ci-dessous, appelée aussi par le script lui-même)
#: refuse une entrée qui ne correspondrait plus à rien.
PRODUIT_AILLEURS = {
    'documents': {
        'export_projet_json': (
            "format JSON, pas une mise en page HTML : servi par "
            "GET .../export-projet.json/ (apps/calepinage/views/"
            "documents.py), hors du registre MISES_EN_PAGE qui ne couvre "
            "que les pièces HTML+PDF partagées avec l'aperçu (CALX323)."
        ),
        'diagramme_pertes': (
            "image SVG, pas une mise en page HTML : servie par "
            "GET .../diagramme-pertes.svg/ (apps/calepinage/views/"
            "documents.py, CALX308), hors du registre MISES_EN_PAGE."
        ),
        'dossier_fin_chantier': (
            "fusion d'octets de plusieurs pièces déjà rendues "
            "(pack_technique.DOSSIER_FIN_CHANTIER, CALX319), pas une mise "
            "en page HTML unique : servi par POST .../dossier-fin-"
            "chantier/ (apps/calepinage/views/documents.py), hors du "
            "registre MISES_EN_PAGE."
        ),
        'rapport_ombrage': (
            "a SON PROPRE rendu (apps/calepinage/services/rapport_ombrage."
            "py — rendre_rapport_ombrage/html_du_rapport_ombrage) et SON "
            "PROPRE endpoint GET .../rapport-ombrage.pdf/ (apps/"
            "calepinage/views/documents.py) — pas encore branché sur le "
            "registre partagé MISES_EN_PAGE (CALX323, l'aperçu HTML), donc "
            "invisible de CETTE liste précise ; crochet pour la phase 2 : "
            "y ajouter la ligne MISES_EN_PAGE['rapport_ombrage']."
        ),
    },
}


def _arbre(chemin):
    return ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))


def _chaine(noeud):
    """La chaîne littérale portée par ``noeud``, ou ``None``."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    return None


def _codes_tuple_de_tuples(arbre, nom_variable):
    """Les CODES (premier élément) d'une déclaration
    ``NOM = ((code, libelle, ...), ...)`` — ``SPEC_PIECES``,
    ``PIECES_PRODUITES`` et ``_DEFINITIONS_DOCUMENTS`` partagent cette
    forme. Lève ``LookupError`` en NOMMANT la variable si elle n'existe
    plus : un renommage de la déclaration doit casser CETTE garde, pas
    passer inaperçu en rendant une liste vide."""
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Assign)
                and len(noeud.targets) == 1
                and isinstance(noeud.targets[0], ast.Name)
                and noeud.targets[0].id == nom_variable
                and isinstance(noeud.value, (ast.Tuple, ast.List))):
            codes = []
            for element in noeud.value.elts:
                if isinstance(element, (ast.Tuple, ast.List)) and element.elts:
                    code = _chaine(element.elts[0])
                    if code:
                        codes.append(code)
            return codes
    raise LookupError(
        "variable « %s » introuvable — déclaration renommée ou retirée."
        % nom_variable)


def _cles_dict_litteral(noeud_dict):
    return [chaine for chaine in (_chaine(cle) for cle in noeud_dict.keys)
            if chaine]


def _cles_return_dict(arbre, nom_fonction):
    """Les CLÉS du ``dict`` littéral que
    ``def nom_fonction(...): ... return {...}`` retourne."""
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == nom_fonction:
            for enfant in ast.walk(noeud):
                if (isinstance(enfant, ast.Return)
                        and isinstance(enfant.value, ast.Dict)):
                    return _cles_dict_litteral(enfant.value)
            raise LookupError(
                "fonction « %s » trouvée mais aucun `return {...}` "
                "littéral dedans." % nom_fonction)
    raise LookupError("fonction « %s » introuvable." % nom_fonction)


def _cles_registre_module(arbre, nom_variable):
    """Les CLÉS de ``NOM = {...}`` (dict littéral module-level) PLUS chaque
    ``NOM['x'] = ...`` (assignation par indice) trouvée ailleurs dans le
    fichier — le patron EXACT de ``MISES_EN_PAGE`` dans
    ``services/documents/__init__.py`` (une entrée initiale, puis une ligne
    ajoutée par chaque tâche suivante du lot, ``__init__.py`` docstring :
    « surface APPEND-ONLY »)."""
    cles = []
    trouve = False
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Assign) and len(noeud.targets) == 1):
            continue
        cible = noeud.targets[0]
        if (isinstance(cible, ast.Name) and cible.id == nom_variable
                and isinstance(noeud.value, ast.Dict)):
            cles.extend(_cles_dict_litteral(noeud.value))
            trouve = True
        elif (isinstance(cible, ast.Subscript)
              and isinstance(cible.value, ast.Name)
              and cible.value.id == nom_variable):
            cle = _chaine(cible.slice)
            if cle:
                cles.append(cle)
                trouve = True
    if not trouve:
        raise LookupError("registre « %s » introuvable." % nom_variable)
    return cles


#: ``(famille, chemin, fonction_codes_declares, fonction_codes_rendus)`` —
#: les trois paires DÉCLARATION/RENDU du module, chacune parsée depuis SA
#: propre AST (un seul fichier lu par paire).
FAMILLES = (
    ('pack_technique',
     CALEPINAGE / 'services' / 'pack_technique.py',
     lambda arbre: _codes_tuple_de_tuples(arbre, 'SPEC_PIECES'),
     lambda arbre: _cles_return_dict(arbre, '_rendus')),
    ('reglementaire',
     CALEPINAGE / 'services' / 'reglementaire.py',
     lambda arbre: _codes_tuple_de_tuples(arbre, 'PIECES_PRODUITES'),
     lambda arbre: _cles_return_dict(arbre, '_rendus_du_module')),
    ('documents',
     CALEPINAGE / 'services' / 'documents' / '__init__.py',
     lambda arbre: _codes_tuple_de_tuples(arbre, '_DEFINITIONS_DOCUMENTS'),
     lambda arbre: _cles_registre_module(arbre, 'MISES_EN_PAGE')),
)


def ecarts_de_famille(declares, rendus, exemptions):
    """``(manquants, orphelins)`` pour UNE famille — jamais un total figé."""
    manquants = [code for code in declares
                 if code not in rendus
                 and not (exemptions.get(code) or '').strip()]
    orphelins = [code for code in rendus if code not in declares]
    return manquants, orphelins


def problemes_de_famille(nom, nom_fichier, declares, rendus, exemptions):
    """Les messages d'écart pour UNE famille DÉJÀ résolue en listes de
    codes — PURE, sans fichier ni AST, pour rester testable en une ligne."""
    problemes = []
    for code in exemptions:
        if code not in declares:
            problemes.append(
                "%s (%s) : l'exemption « %s » (PRODUIT_AILLEURS) ne "
                "correspond à AUCUN code déclaré — filtre mort, à retirer."
                % (nom, nom_fichier, code))

    manquants, orphelins = ecarts_de_famille(declares, rendus, exemptions)
    for code in manquants:
        problemes.append(
            "%s (%s) : « %s » est DÉCLARÉ sans rendu ET sans motif "
            "« produit ailleurs »." % (nom, nom_fichier, code))
    for code in orphelins:
        problemes.append(
            "%s (%s) : « %s » a un rendu mais n'est déclaré NULLE PART — "
            "code mort qui se croit vivant." % (nom, nom_fichier, code))
    return problemes


def verifier(familles=FAMILLES, produit_ailleurs=PRODUIT_AILLEURS):
    """La liste des PROBLÈMES trouvés (vide = garde verte) sur TOUT le
    dépôt réel — ``familles``/``produit_ailleurs`` restent substituables
    (essais purs, aucun fichier réel touché)."""
    problemes = []
    for nom, chemin, get_declares, get_rendus in familles:
        arbre = _arbre(chemin)
        declares = get_declares(arbre)
        rendus = get_rendus(arbre)
        problemes.extend(problemes_de_famille(
            nom, chemin.name, declares, rendus,
            produit_ailleurs.get(nom, {})))
    return problemes


def main():
    try:
        problemes = verifier()
    except LookupError as erreur:
        print('check_documents_calepinage : %s' % erreur)
        return 1
    if problemes:
        print('check_documents_calepinage : %d écart(s) trouvé(s) :'
              % len(problemes))
        for probleme in problemes:
            print(' - %s' % probleme)
        return 1
    print('check_documents_calepinage : OK — chaque document déclaré a un '
          'rendu (ou un motif « produit ailleurs » vérifié), aucun rendu '
          'orphelin.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
