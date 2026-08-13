#!/usr/bin/env python3
"""Garde de VOCABULAIRE a source declaree — OPT-IN, zero faux positif par construction.

POURQUOI CETTE FORME ET PAS UNE AUTRE (PACT159 — mesure, pas opinion)
---------------------------------------------------------------------
La detection par RESSEMBLANCE est disqualifiee par la mesure : 18 listes de
choix frontend « candidates » trouvees automatiquement, 13 FAUX POSITIFS
(72 %). Et le cas fondateur — la liste de `ExigencesPage` — ne partageait
ZERO valeur avec le champ serveur qu'elle etait censee refleter : aucune
similarite ne pouvait le voir. Une garde qui crie au loup 3 fois sur 4 et rate
le seul vrai defaut n'est pas une garde ; elle finit desactivee.

LA SEULE FORME VIABLE EST DECLARATIVE. L'auteur de la liste DIT d'ou vient son
vocabulaire, avec un marqueur machine pose juste au-dessus :

    // source-choix: rh.DossierEmploye.motif_sortie
    const MOTIFS = [
      { value: 'demission', label: 'Démission' },
      ...
    ]

Pour un vocabulaire qui ne vit pas dans un `TextChoices` (fabrique, module de
constantes), le marqueur porte le chemin de la constante :

    // source-choix: ao.fabrique.approvisionnement.GRAVITES

REGLE ABSOLUE : SEULES LES LISTES MARQUEES SONT VERIFIEES. Une liste sans
marqueur n'est JAMAIS un rouge — c'est ce qui rend le taux de faux positifs nul
par construction, et c'est ce qui remplace les ~80 promesses en PROSE du depot
(« aligné sur X », « miroir de Y ») : une prose ne se verifie pas, un marqueur
si. Le commentaire d'`EmployeDetail.jsx` en est l'exemple : il PROMETTAIT
l'alignement sur `DossierEmploye.MotifSortie` et rien ne le verifiait.

LE PIEGE RESOLU : LE NOM QUALIFIE. `choices=Statut.choices` ecrit DANS
`class DossierEmploye` designe la classe IMBRIQUEE `DossierEmploye.Statut`, pas
un `Statut` de niveau module. Resoudre par nom simple donnait 6 faux candidats
mesures (plusieurs modeles declarent un `Statut` ou un `Type` different). La
resolution ci-dessous part donc TOUJOURS du modele porteur, puis remonte.

SENS DE LA COMPARAISON (delibere). Seul « la liste front declare une valeur que
le serveur ne connait pas » est un rouge : c'est le defaut qui casse un
enregistrement (400) ou un filtre (0 resultat). L'inverse — le serveur connait
une valeur que l'ecran n'offre pas — est un CHOIX d'ecran legitime (un
formulaire de sortie n'offre pas les statuts d'entree) et ne rougit jamais.

Usage :
    python scripts/check_choices_declares.py            # garde CI
    python scripts/check_choices_declares.py --stats    # + inventaire chiffre
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_ROOT = ROOT / "backend" / "django_core"
APPS_ROOT = DJANGO_ROOT / "apps"
FRONT_SRC = ROOT / "frontend" / "src"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_api_contract import scan_js  # noqa: E402

# `// source-choix: rh.DossierEmploye.motif_sortie`
MARQUEUR = re.compile(r"//\s*source-choix\s*:\s*(?P<cible>[A-Za-z_][\w.]*)")
# Un nom TOUT_EN_MAJUSCULES en dernier segment designe une CONSTANTE de module ;
# tout le reste est lu comme `app.Modele.champ`.
_CONSTANTE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# `{ value: 'x', label: '…' }` — la forme du depot.
_VALEUR = re.compile(r"""\bvalue\s*:\s*(?P<q>['"])(?P<v>[^'"]*)(?P=q)""")
_CHAINE = re.compile(r"""(?P<q>['"])(?P<v>[^'"]*)(?P=q)""")


# ===========================================================================
# 1. Cote serveur : resoudre le vocabulaire declare
# ===========================================================================

def _module_tree(chemin: Path):
    try:
        return ast.parse(chemin.read_text(encoding="utf-8", errors="replace"),
                         filename=str(chemin))
    except (OSError, SyntaxError):
        return None


def _classes_de(noeud) -> dict:
    return {item.name: item for item in noeud.body if isinstance(item, ast.ClassDef)}


def _valeurs_de_textchoices(classe: ast.ClassDef) -> set:
    """{'demission', …} — la 1re composante de chaque membre du TextChoices."""
    valeurs = set()
    for item in classe.body:
        if not isinstance(item, ast.Assign) or len(item.targets) != 1:
            continue
        cible = item.targets[0]
        if not isinstance(cible, ast.Name) or cible.id.startswith("_"):
            continue
        valeur = item.value
        if isinstance(valeur, ast.Tuple) and valeur.elts:
            valeur = valeur.elts[0]
        if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
            valeurs.add(valeur.value)
    return valeurs


def _valeurs_de_liste(noeud) -> set | None:
    """[( 'x', 'Label'), …] ou ['x', …] -> {'x', …} ; None si illisible."""
    if not isinstance(noeud, (ast.List, ast.Tuple)):
        return None
    valeurs = set()
    for element in noeud.elts:
        if isinstance(element, (ast.Tuple, ast.List)) and element.elts:
            element = element.elts[0]
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            valeurs.add(element.value)
        else:
            return None
    return valeurs or None


def _dotted(noeud) -> list | None:
    """`DossierEmploye.MotifSortie.choices` -> ['DossierEmploye','MotifSortie','choices']"""
    parties = []
    courant = noeud
    while isinstance(courant, ast.Attribute):
        parties.append(courant.attr)
        courant = courant.value
    if not isinstance(courant, ast.Name):
        return None
    parties.append(courant.id)
    parties.reverse()
    return parties


def _resoudre_reference(noeud, modele: ast.ClassDef, arbre, constantes: dict):
    """Valeurs designees par l'expression `choices=…`, ou None si incertain.

    LE PIEGE QUALIFIE : un nom SIMPLE ecrit dans le corps du modele designe
    d'abord la classe IMBRIQUEE de CE modele. Resoudre par nom simple au niveau
    module donnait 6 faux candidats mesures.
    """
    parties = _dotted(noeud)
    if parties is None:
        valeurs = _valeurs_de_liste(noeud)
        return valeurs
    if parties[-1] == "choices":
        parties = parties[:-1]
    if not parties:
        return None
    imbriquees = _classes_de(modele)
    sommet = _classes_de(arbre)
    if len(parties) == 1:
        nom = parties[0]
        if nom in imbriquees:                 # `Statut` = DossierEmploye.Statut
            return _valeurs_de_textchoices(imbriquees[nom])
        if nom in constantes:
            return _valeurs_de_liste(constantes[nom])
        if nom in sommet:
            return _valeurs_de_textchoices(sommet[nom])
        return None
    porteur = sommet.get(parties[0])
    if porteur is None:
        return None
    for maillon in parties[1:]:
        suivant = _classes_de(porteur).get(maillon)
        if suivant is None:
            return None
        porteur = suivant
    return _valeurs_de_textchoices(porteur)


def _constantes_de_module(arbre) -> dict:
    out = {}
    for item in arbre.body:
        if isinstance(item, ast.Assign):
            for cible in item.targets:
                if isinstance(cible, ast.Name):
                    out[cible.id] = item.value
    return out


def valeurs_serveur(cible: str):
    """(valeurs, description lisible) ou (None, motif de l'echec)."""
    parties = cible.split(".")
    if len(parties) < 2:
        return None, f"cible `{cible}` illisible (attendu `app.Modele.champ`)"

    if _CONSTANTE.match(parties[-1]):
        # `ao.fabrique.approvisionnement.GRAVITES`
        chemin = APPS_ROOT.joinpath(*parties[:-1]).with_suffix(".py")
        if not chemin.is_file():
            chemin = APPS_ROOT.joinpath(*parties[:-1]) / "__init__.py"
        if not chemin.is_file():
            return None, f"module introuvable pour `{cible}` ({chemin.name})"
        arbre = _module_tree(chemin)
        if arbre is None:
            return None, f"module illisible pour `{cible}`"
        constante = _constantes_de_module(arbre).get(parties[-1])
        if constante is None:
            return None, f"constante `{parties[-1]}` absente de {chemin.name}"
        valeurs = _valeurs_de_liste(constante)
        if valeurs is None:
            return None, (f"constante `{parties[-1]}` de {chemin.name} n'est pas "
                          "une liste de valeurs litterales")
        return valeurs, f"{cible} ({len(valeurs)} valeurs)"

    if len(parties) != 3:
        return None, (f"cible `{cible}` illisible (attendu `app.Modele.champ` "
                      "ou un chemin de constante `app.module.CONSTANTE`)")
    app, modele_nom, champ = parties
    chemin = APPS_ROOT / app / "models.py"
    if not chemin.is_file():
        return None, f"application `{app}` sans models.py (cible `{cible}`)"
    arbre = _module_tree(chemin)
    if arbre is None:
        return None, f"models.py de `{app}` illisible"
    modele = _classes_de(arbre).get(modele_nom)
    if modele is None:
        return None, f"modele `{modele_nom}` absent de apps/{app}/models.py"
    constantes = _constantes_de_module(arbre)
    for item in modele.body:
        if not isinstance(item, ast.Assign) or len(item.targets) != 1:
            continue
        cible_nom = item.targets[0]
        if not isinstance(cible_nom, ast.Name) or cible_nom.id != champ:
            continue
        if not isinstance(item.value, ast.Call):
            return None, f"champ `{champ}` de `{modele_nom}` n'est pas un champ Django"
        for kw in item.value.keywords:
            if kw.arg != "choices":
                continue
            valeurs = _resoudre_reference(kw.value, modele, arbre, constantes)
            if valeurs is None:
                return None, (f"`{cible}` : les `choices` ne sont pas resolubles "
                              "statiquement (source non figee)")
            return valeurs, f"{cible} ({len(valeurs)} valeurs)"
        return None, f"champ `{champ}` de `{modele_nom}` ne declare aucun `choices`"
    return None, f"champ `{champ}` absent du modele `{modele_nom}` (apps/{app}/models.py)"


# ===========================================================================
# 2. Cote frontend : lire la liste marquee
# ===========================================================================

# Le marqueur porte sur la liste qui le SUIT IMMEDIATEMENT. Sans cette borne,
# un marqueur pose devant un objet (et non un tableau) irait chercher la
# premiere liste du fichier, 300 lignes plus bas : un rouge sur du code sain.
PORTEE_MARQUEUR = 400


def _bloc_de_liste(masque: str, depart: int):
    """(debut, fin) du premier `[ … ]` equilibre apres `depart`, ou None."""
    debut = masque.find("[", depart)
    if debut < 0 or debut - depart > PORTEE_MARQUEUR:
        return None
    profondeur = 0
    for index in range(debut, len(masque)):
        caractere = masque[index]
        if caractere in "[{(":
            profondeur += 1
        elif caractere in "])}":
            profondeur -= 1
            if profondeur == 0:
                return (debut, index + 1)
    return None


def valeurs_frontend(code: str, masque: str, depart: int):
    """({valeurs}, None) ou (None, motif) — la liste marquee, lue du source."""
    bornes = _bloc_de_liste(masque, depart)
    if bornes is None:
        return None, ("le marqueur `source-choix` ne precede aucune liste `[ … ]` "
                      "lisible")
    bloc = code[bornes[0]:bornes[1]]
    valeurs = {trouve.group("v") for trouve in _VALEUR.finditer(bloc)}
    if valeurs:
        return valeurs, None
    if "{" in bloc:
        return None, ("liste d'objets sans cle `value:` — un marqueur "
                      "`source-choix` exige une liste lisible par machine")
    valeurs = {trouve.group("v") for trouve in _CHAINE.finditer(bloc)}
    if valeurs:
        return valeurs, None
    return None, "liste marquee vide ou illisible"


def fichiers_frontend(racine: Path = None):
    racine = FRONT_SRC if racine is None else racine
    if not racine.is_dir():
        return []
    vus = []
    for motif in ("*.js", "*.jsx", "*.mjs"):
        for chemin in sorted(racine.rglob(motif)):
            if "node_modules" in chemin.parts:
                continue
            vus.append(chemin)
    return vus


# ===========================================================================
# 3. Rapprochement
# ===========================================================================

def analyser(racine: Path = None):
    """([(fichier, ligne, cible, motif)], nombre de listes marquees verifiees)."""
    constats, verifiees = [], 0
    for chemin in fichiers_frontend(racine):
        try:
            source = chemin.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "source-choix" not in source:
            continue
        code, _, masque = scan_js(source)
        relatif = (chemin.relative_to(ROOT).as_posix()
                   if chemin.is_relative_to(ROOT) else chemin.as_posix())
        for trouve in MARQUEUR.finditer(source):
            ligne = source.count("\n", 0, trouve.start()) + 1
            cible = trouve.group("cible")
            attendues, description = valeurs_serveur(cible)
            if attendues is None:
                constats.append((relatif, ligne, cible, description))
                continue
            trouvees, motif = valeurs_frontend(code, masque, trouve.end())
            if trouvees is None:
                constats.append((relatif, ligne, cible, motif))
                continue
            verifiees += 1
            inventees = sorted(trouvees - attendues)
            if inventees:
                constats.append((
                    relatif, ligne, cible,
                    f"valeur(s) INVENTEE(S) {', '.join(repr(v) for v in inventees)} : "
                    f"le champ `{cible}` ne les connait pas "
                    f"(il accepte : {', '.join(sorted(attendues))})"))
    return constats, verifiees


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Garde de vocabulaire a source declaree (opt-in, PACT159).")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args(argv)

    constats, verifiees = analyser()
    if args.stats:
        print(f"Listes de choix frontend a source DECLAREE : {verifiees}.")
        print(f"Divergences : {len(constats)}.")

    if constats:
        print(f"\nECHEC : {len(constats)} liste(s) de choix frontend divergent de "
              f"la source qu'elles DECLARENT.\n")
        for relatif, ligne, cible, motif in sorted(constats):
            print(f"  {relatif}:{ligne}  (// source-choix: {cible})")
            print(f"      {motif}")
        print("\nUne liste marquee `// source-choix:` PROMET que son vocabulaire "
              "vient du serveur. Corriger la liste, corriger le modele, ou "
              "retirer le marqueur (une liste NON marquee n'est jamais "
              "controlee — cette garde est volontairement opt-in).")
        return 1

    print(f"OK : {verifiees} liste(s) de choix frontend a source declaree, "
          "toutes alignees sur le vocabulaire du serveur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
