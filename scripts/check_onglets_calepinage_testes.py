#!/usr/bin/env python3
"""GARDE CI (stage-names) — CALX383 : un onglet du rail arrive avec son test.

CONSTAT. `frontend/src/features/calepinage/atelier/onglets.js` (CALX1) est le
registre DÉCLARATIF de chaque onglet de l'atelier : `{cle, libelle, groupe,
ordre, composant}`, `composant` étant `lazy(() => import('<chemin>'))`. Rien
n'oblige mécaniquement un onglet neuf à porter un test — mesuré le 23/09/2026,
sur 27 entrées du registre, 22 ont un `*.test.jsx` posé À CÔTÉ de leur
composant et 5 n'en ont AUCUN (`SaisiePente`, `ModeTerrain`, `Ombriere`,
`HorizonPanel`, `CourseSoleil` — cinq panneaux « Site » antérieurs à CALX1, qui
prédatent la discipline que ce registre impose). Cette garde empêche la
RÉCIDIVE (aucun onglet NEUF sans test) sans prétendre réparer d'un coup un
passif déjà mesuré et nommé — même principe que `check_services_appeles.py` /
`check_ecrans_atteignables.py` / `check_calepinage_actions_consommees.py`
(CALX381) : le passif gèle dans `scripts/onglets_calepinage_sans_test_allow.txt`,
UNE ligne par `cle`, et la liste ne peut que RÉTRÉCIR.

TROIS GARDES DANS CE SCRIPT :
  1. Chaque `cle` du registre a un `*.test.jsx` à côté du fichier RÉSOLU par
     son `import()` paresseux (littéral — l'analyse est une lecture de
     SOURCE, jamais une résolution Webpack/Vite) — sauf passif gelé.
  2. Aucune `cle` n'est déclarée deux fois (TOUJOURS enforcé, zéro passif
     possible : une clé dupliquée casse `ongletParCle` en silence, en ne
     rendant jamais que la PREMIÈRE correspondance).
  3. `atelier/Rail.jsx` ne contourne jamais le registre : tout fichier
     `.jsx` du dossier `atelier/` qu'il importerait DIRECTEMENT (hors
     `./onglets`) doit être le composant d'UN onglet déclaré — sinon un
     panneau vivrait dans le rail sans jamais apparaître dans le registre,
     donc sans jamais avoir de route ni de test garantis par cette garde.

Usage
-----
    python scripts/check_onglets_calepinage_testes.py
    python scripts/check_onglets_calepinage_testes.py --write-baseline
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ATELIER_DIR = ROOT / "frontend" / "src" / "features" / "calepinage" / "atelier"
ONGLETS_PATH = ATELIER_DIR / "onglets.js"
RAIL_PATH = ATELIER_DIR / "Rail.jsx"
BASELINE_PATH = ROOT / "scripts" / "onglets_calepinage_sans_test_allow.txt"

# Une entrée du registre : `{ cle: '...', ... composant: lazy(() =>
# import('...')) }` — champs dans un ordre STABLE (voir l'en-tête d'onglets.js)
# mais on ne suppose que `cle` AVANT `composant`, jamais un ordre exact de
# champs intermédiaires (`libelle`/`groupe`/`ordre` peuvent bouger).
RE_ENTREE = re.compile(
    r"\{\s*cle:\s*'(?P<cle>[^']+)'"
    r"(?:(?!\}).)*?"
    r"composant:\s*lazy\(\(\)\s*=>\s*import\('(?P<chemin>[^']+)'\)\)",
    re.S,
)


def sans_commentaires(texte: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", "", texte)


def _ligne_de(texte: str, position: int) -> int:
    return texte.count("\n", 0, position) + 1


def entrees_registre(source: str | None = None) -> list:
    """[{cle, chemin, ligne}, ...] dans l'ordre du fichier (PAS trié par
    `ordre` — cette garde ne s'intéresse qu'à la déclaration, jamais à
    l'affichage)."""
    if source is None:
        source = ONGLETS_PATH.read_text(encoding="utf-8")
    code = sans_commentaires(source)
    trouvees = []
    for m in RE_ENTREE.finditer(code):
        trouvees.append({
            "cle": m.group("cle"),
            "chemin": m.group("chemin"),
            "ligne": _ligne_de(code, m.start()),
        })
    return trouvees


def resoudre_composant(chemin_import: str, depuis: Path | None = None) -> Path:
    """Le fichier `.jsx` RÉSOLU d'un `import('<chemin>')` littéral — jamais
    une résolution de bundler, une simple jointure de chemin relatif.

    `depuis` est relu à L'APPEL (jamais une valeur par défaut figée à la
    définition) : un test qui monkeypatch `ATELIER_DIR` doit voir son
    changement pris en compte, exactement comme `test_check_api_contract.py`
    le fait pour `cac.ROOT`."""
    racine = depuis if depuis is not None else ATELIER_DIR
    return (racine / chemin_import).resolve().with_suffix(".jsx")


def fichier_test_de(composant: Path) -> Path:
    return composant.with_suffix("").with_suffix(".test.jsx")


# ===========================================================================
# Garde 3 : Rail.jsx ne contourne jamais le registre
# ===========================================================================

RE_IMPORT_RELATIF = re.compile(r"""import\s+[^;'"]*from\s+['"](\.[^'"]+)['"]""")


def composants_importes_par_le_rail() -> list:
    """Fichiers `.jsx` de `atelier/` importés DIRECTEMENT par `Rail.jsx`
    (hors `./onglets`, hors lui-même) — la porte que cette garde ferme."""
    if not RAIL_PATH.is_file():
        return []
    code = sans_commentaires(RAIL_PATH.read_text(encoding="utf-8"))
    trouves = []
    for m in RE_IMPORT_RELATIF.finditer(code):
        chemin = m.group(1)
        if chemin in ("./onglets",):
            continue
        resolu = resoudre_composant(chemin, depuis=RAIL_PATH.parent)
        try:
            resolu.relative_to(ATELIER_DIR)
        except ValueError:
            continue  # composant hors atelier/ : hors du périmètre de cette garde
        if resolu.is_file():
            trouves.append(resolu)
    return trouves


# ===========================================================================
# Base de reference (garde 1 uniquement — les gardes 2 et 3 n'ont pas de passif)
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_onglets_calepinage_testes.py — DETTE HISTORIQUE,
# RIEN D'AUTRE (CALX383).
#
# Chaque ligne est la `cle` d'un onglet du registre `atelier/onglets.js` dont
# le composant RESOLU n'a PAS de `*.test.jsx` a cote de lui. Cette liste gele
# l'etat du jour : la garde empeche la RECIDIVE (aucun onglet NEUF sans test),
# elle ne repare pas le passif — chaque ligne drainee est un onglet qui a enfin
# recu son test.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - poser le test puis `python scripts/check_onglets_calepinage_testes.py
#     --write-baseline` retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# Format : `<cle>  # <raison datee>`.
"""

_LIGNE_BASE = re.compile(r"^(?P<cle>\S+)\s*(?:#.*)?$")


def charger_base(path: Path | None = None) -> set:
    path = path or BASELINE_PATH
    if not path.is_file():
        return set()
    base = set()
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        m = _LIGNE_BASE.match(ligne)
        if m:
            base.add(m.group("cle"))
    return base


def ecrire_base(cles: set, path: Path | None = None):
    path = path or BASELINE_PATH
    corps = "\n".join(
        f"{cle}  # sans test au 23/09/2026 (CALX383)" for cle in sorted(cles)
    )
    path.write_text(
        ENTETE_BASE + (corps + "\n" if corps else ""),
        encoding="utf-8", newline="\n",
    )


# ===========================================================================
# Analyse
# ===========================================================================

def analyse() -> dict:
    entrees = entrees_registre()

    doublons = {}
    for e in entrees:
        doublons.setdefault(e["cle"], []).append(e["ligne"])
    cles_dupliquees = {cle: lignes for cle, lignes in doublons.items() if len(lignes) > 1}

    sans_test = []
    composants_registres = set()
    for e in entrees:
        composant = resoudre_composant(e["chemin"])
        composants_registres.add(composant)
        if not composant.is_file():
            sans_test.append({**e, "motif": f"composant introuvable : {composant}"})
            continue
        if not fichier_test_de(composant).is_file():
            sans_test.append({**e, "motif": None})

    bypass = [
        c for c in composants_importes_par_le_rail() if c not in composants_registres
    ]

    return {
        "entrees": entrees,
        "cles_dupliquees": cles_dupliquees,
        "sans_test": sans_test,
        "bypass": bypass,
    }


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde « onglet du rail sans test » (CALX383).")
    parser.add_argument(
        "--write-baseline", action="store_true",
        help="retire de la base les onglets desormais testes",
    )
    parser.add_argument(
        "--autoriser-croissance", action="store_true",
        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes",
    )
    args = parser.parse_args(argv)

    resultat = analyse()

    if not resultat["entrees"]:
        print("\nECHEC : aucune entree lue dans atelier/onglets.js. Soit le "
              "registre a change de forme, soit la lecture a cesse de "
              "fonctionner — dans les deux cas la garde a cesse de garder.")
        return 1

    echec = False

    if resultat["cles_dupliquees"]:
        echec = True
        print("\nECHEC : cle(s) dupliquee(s) dans atelier/onglets.js "
              "(ongletParCle ne renverrait jamais que la PREMIERE) :")
        for cle, lignes in sorted(resultat["cles_dupliquees"].items()):
            print(f"  '{cle}' déclarée aux lignes {lignes}")

    if resultat["bypass"]:
        echec = True
        print("\nECHEC : Rail.jsx importe directement un composant de "
              "atelier/ qui ne figure dans AUCUNE entree du registre "
              "(un onglet qui contourne onglets.js) :")
        for chemin in resultat["bypass"]:
            print(f"  {chemin.relative_to(ROOT).as_posix()}")

    base = charger_base()
    cles_sans_test = {e["cle"] for e in resultat["sans_test"]}

    if args.write_baseline:
        ajouts = cles_sans_test - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
            for cle in sorted(ajouts)[:20]:
                print(f"  + {cle}")
            print("Posez le test, ou assumez la dette avec --autoriser-croissance.")
            return 1
        ecrire_base(cles_sans_test)
        print(f"Base de reference reecrite : {BASELINE_PATH} "
              f"({len(cles_sans_test)} entree(s), "
              f"{len(base - cles_sans_test)} retiree(s)).")
        return 0 if not echec else 1

    nouveaux = [e for e in resultat["sans_test"] if e["cle"] not in base]
    corriges = base - cles_sans_test

    if nouveaux:
        echec = True
        print(f"\nECHEC : {len(nouveaux)} onglet(s) sans test (hors base de "
              f"reference) :")
        for e in nouveaux:
            attendu = fichier_test_de(resoudre_composant(e["chemin"]))
            motif = e["motif"] or f"fichier attendu manquant : {attendu.relative_to(ROOT).as_posix()}"
            print(f"  '{e['cle']}' (atelier/onglets.js:{e['ligne']}) — {motif}")
        print("\nQUE FAIRE :")
        print("  - posez le `*.test.jsx` à côté du composant, qui le MONTE ;")
        print("  - ou, dette assumee a drainer plus tard, "
              "`--write-baseline --autoriser-croissance` (fondateur).")

    if echec:
        return 1

    print(f"OK : {len(resultat['entrees'])} onglet(s) lu(s), aucune cle "
          f"dupliquee, aucun contournement du registre, aucun NOUVEL onglet "
          f"sans test ({len(base)} dette(s) historique(s) gelee(s), dont "
          f"{len(corriges)} desormais testee(s)).")
    if corriges:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_onglets_calepinage_testes.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
