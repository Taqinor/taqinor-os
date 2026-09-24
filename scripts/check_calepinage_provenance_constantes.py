#!/usr/bin/env python3
"""GARDE CI (stage-names) — CALX384 : provenance des constantes numériques du
paquet `apps/calepinage/services/`.

CONSTAT. `services/lestage.py:85` déclare `NOMBRES_DE_FORME` et son test de
surface (`tests/test_lestage_parametre.py:200`) refuse tout autre littéral
numérique — pour CE fichier seulement. Mesuré ce jour sur l'ENSEMBLE du
paquet (130 modules non-test, `services/`, `services/documents/`,
`services/etapes/`, `services/rapport/`) : la discipline est en réalité DÉJÀ
tenue partout — chaque constante numérique de niveau module est introduite
par un commentaire — À CONDITION de compter un commentaire `#:` comme
couvrant le BLOC CONTIGU qu'il introduit, pas seulement la ligne suivante.
Une lecture naïve « la ligne du dessus » produit des faux positifs vérifiés :
`thermique.py:90 NOCT_TEMPERATURE_AIR_C` (précédée de `NOCT_IRRADIANCE_W_M2`,
elle-même sous le `#:` de tête), `pompage.py:29 TENSION_TRI_V` (sous le même
patron), `electrique.py:1721 TOLERANCE_LONGUEUR_PCT` (sous
`TOLERANCE_LONGUEUR_MODULES`, elle-même sous son `#:` de tête).

CE QUE CETTE GARDE FAIT. AST sur chaque fichier : toute affectation de
NIVEAU MODULE dont TOUTES les cibles sont des noms ENTIÈREMENT MAJUSCULES
(``^[A-Z][A-Z0-9_]*$``) et dont la valeur contient, n'importe où dans son
arbre (scalaire, tuple, liste, dict), au moins un littéral NUMÉRIQUE
(``int``/``float``, jamais un booléen) doit être « couverte » par une
provenance :
  - un commentaire directement au-dessus (le cas simple) ; ou
  - la fin d'une CHAÎNE CONTIGUË de constantes de module (numériques ou non)
    qui remonte, sans ligne blanche ni autre instruction interposée, jusqu'à
    un commentaire de tête (le patron `#:` mesuré ci-dessus).
Une ligne blanche, ou toute autre instruction, CASSE la chaîne : au-delà,
plus aucune provenance n'est héritée.

BASELINE VIDE PAR PRINCIPE. La discipline est déjà tenue à 100 % au
23/09/2026 (0 constante nue) : `scripts/calepinage_provenance_constantes_allow.txt`
n'existe pas et n'est jamais créé — le premier littéral nu qui apparaîtra
rougira la CI directement, sans détour par un passif à gérer.

Usage
-----
    python scripts/check_calepinage_provenance_constantes.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = (
    ROOT / "backend" / "django_core" / "apps" / "calepinage" / "services"
)

RE_CONSTANTE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _est_nom_constante(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name) and RE_CONSTANTE.match(node.id):
        return node.id
    return None


def _cibles_constantes(assign: ast.Assign) -> list:
    noms = []
    for cible in assign.targets:
        nom = _est_nom_constante(cible)
        if nom is None:
            return []
        noms.append(nom)
    return noms


def _contient_un_nombre(valeur: ast.AST) -> bool:
    for node in ast.walk(valeur):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            return True
    return False


def _fichiers_a_verifier() -> list:
    if not SERVICES_DIR.is_dir():
        return []
    fichiers = []
    for chemin in SERVICES_DIR.rglob("*.py"):
        if chemin.name.startswith(("test_", "tests_")) or chemin.name == "tests.py":
            continue
        fichiers.append(chemin)
    return sorted(fichiers)


def _assignations_de_module(tree: ast.Module) -> list:
    """Chaque affectation de NIVEAU MODULE à un(des) nom(s) entièrement
    MAJUSCULES, quelle que soit sa valeur (numérique ou non — un maillon non
    numérique participe quand même à une chaîne contiguë, cf. l'en-tête)."""
    sorties = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        noms = _cibles_constantes(node)
        if noms:
            sorties.append(node)
    return sorties


def _couverte(assign: ast.Assign, fin_par_ligne: dict, lignes: list) -> bool:
    """Remonte la chaîne contiguë de constantes jusqu'à un commentaire de
    tête, une ligne blanche (chaîne cassée) ou une autre instruction."""
    ligne_courante = assign.lineno
    vus = set()
    while True:
        if ligne_courante in vus:
            return False  # garde-fou anti-boucle (ne devrait jamais arriver)
        vus.add(ligne_courante)
        ligne_avant = ligne_courante - 1
        if ligne_avant < 1:
            return False
        texte = lignes[ligne_avant - 1].strip()
        if texte == "":
            return False
        if texte.startswith("#"):
            return True
        precedente = fin_par_ligne.get(ligne_avant)
        if precedente is not None:
            ligne_courante = precedente.lineno
            continue
        return False


def constantes_sans_provenance(chemin: Path) -> list:
    """[(ligne, nom), ...] pour les constantes numériques NUES de ce fichier."""
    try:
        source = chemin.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=str(chemin))
    except SyntaxError:
        return []
    lignes = source.splitlines()

    toutes = _assignations_de_module(tree)
    fin_par_ligne = {a.end_lineno: a for a in toutes}

    trouvees = []
    for assign in toutes:
        noms = _cibles_constantes(assign)
        if not _contient_un_nombre(assign.value):
            continue
        if _couverte(assign, fin_par_ligne, lignes):
            continue
        for nom in noms:
            trouvees.append((assign.lineno, nom))
    return trouvees


def analyse() -> list:
    """[(fichier_relatif, ligne, nom), ...] triés, sur tout le paquet."""
    constats = []
    for chemin in _fichiers_a_verifier():
        for ligne, nom in constantes_sans_provenance(chemin):
            relatif = chemin.relative_to(ROOT).as_posix() if chemin.is_relative_to(ROOT) \
                else chemin.as_posix()
            constats.append((relatif, ligne, nom))
    return sorted(constats)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    fichiers = _fichiers_a_verifier()
    if not fichiers:
        print("\nECHEC : aucun fichier trouvé dans apps/calepinage/services/. "
              "Soit le chemin analysé a bougé, soit la lecture a cessé de "
              "fonctionner — dans les deux cas la garde a cessé de garder.")
        return 1

    constats = analyse()
    if constats:
        print(f"\nECHEC : {len(constats)} constante(s) numérique(s) SANS "
              f"provenance dans apps/calepinage/services/ :\n")
        for fichier, ligne, nom in constats:
            print(f"  {fichier}:{ligne}  {nom}")
        print("\nQUE FAIRE :")
        print("  - poser un commentaire (`#:` ou `#`) directement au-dessus, "
              "ou dans le bloc contigu de constantes qui la précède, "
              "expliquant D'OÙ vient ce nombre (fiche, norme, mesure, "
              "convention d'atelier) ;")
        print("  - cette garde n'a AUCUNE base de passif : le paquet est "
              "propre à 100 % au 23/09/2026, elle n'existe que pour empêcher "
              "la première régression.")
        return 1

    print(f"OK : {len(fichiers)} fichier(s) de apps/calepinage/services/ "
          f"lu(s), aucune constante numérique sans provenance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
