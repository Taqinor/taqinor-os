#!/usr/bin/env python3
"""GARDE CI (stage-names) — ACAL322 : une saisie admise est branchée des DEUX côtés.

CLASSE C-ACAL-050/053/062/065 : une clé que le serveur ADMET (`CHAMPS_ENTREE`
de `services/electrique.py`, et chaque clé des `REGISTRES` de
`services/parametres_cles.py`) sans LECTEUR backend est une saisie que rien ne
consomme ; sans ÉCRIVAIN d'écran (`frontend/src/api/calepinageApi.js` +
`frontend/src/features/calepinage`) c'est un champ que personne ne peut saisir.

Registres : seul un LECTEUR est exigé (l'écran de réglages est générique). Deux
familles de lecteurs, gardées séparées (D-ACAL-47, fondateur 22/11/2026) :
- lecteur SERVEUR = occurrence de la clé dans le code calepinage ou
  `core/electrique` (hors tests, hors de sa propre déclaration) ;
- lecteur ATELIER (réglages seulement) = ACCÈS à la clé par son nom
  (`.cle`, `?.cle`, `['cle']`) dans l'atelier de toiture
  (`apps/web/src/scripts/roofPro11/`, `apps/web/src/lib/`, `.ts`/`.js` hors
  tests) ou dans son relais `frontend/.../atelier/useAtelierBoot.js` (qui lit la
  section `simulation` des réglages et la transmet à l'atelier), commentaires
  retirés : une simple citation ne compte pas.
Un réglage que PERSONNE ne lit reste refusé ; aucune liste d'exceptions.
Lecture : AST pour extraire les clés ; texte pour les occurrences. Écrivain
d'écran = occurrence de la clé dans l'API ou les écrans calepinage (hors tests).

Passif du jour gelé dans `scripts/saisies_electriques_allow.txt` (clé
`entree::<clé>::ecran|lecteur` ou `registre::<section>.<clé>::ecran|lecteur`) :
il ne peut que RÉTRÉCIR (`--write-baseline` refuse d'ajouter) ; une clé morte
fait échouer la garde. `affectation_manuelle` est exceptée : écrite par
`AffectationChaines.jsx`.

Usage :
    python scripts/check_saisies_electriques_branchees.py [--write-baseline]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cliquet  # noqa: E402 — après sys.path/setup() (D-ENF22)

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path("backend") / "django_core" / "apps" / "calepinage"
# ENF15 — les lecteurs des seuils DC/AC vivent dans le noyau electrique partage
# (core/electrique/onduleurs.py, lit `reglages` pour toute societe) : ce sont
# des lecteurs backend a part entiere des cles du registre calepinage.
LECTEURS_CORE = Path("backend") / "django_core" / "core" / "electrique"
ELECTRIQUE = BACKEND / "services" / "electrique.py"
PARAMETRES = BACKEND / "services" / "parametres_cles.py"
FRONT_API = Path("frontend") / "src" / "api" / "calepinageApi.js"
FRONT_FEATURES = Path("frontend") / "src" / "features" / "calepinage"
# D-ACAL-47 — l'atelier de toiture lit des réglages société (ACAL714/715/716).
ATELIER_SOURCES = (Path("apps") / "web" / "src" / "scripts" / "roofPro11",
                   Path("apps") / "web" / "src" / "lib")
# Relais constaté : il lit `p.simulation.<clé>` de l'API et le passe à l'atelier
# (`opts.reglagesAtelier`).
ATELIER_RELAIS = Path("frontend") / "src" / "features" / "calepinage" / "atelier" / "useAtelierBoot.js"
BASELINE = ROOT / "scripts" / "saisies_electriques_allow.txt"
EXCEPTEES = {"entree::affectation_manuelle"}  # écrite par AffectationChaines.jsx
ENTETE = (
    "# Base de reference de check_saisies_electriques_branchees.py (ACAL322).\n"
    "# Une ligne = une cle admise par le serveur SANS ecran (ecrivain) ou SANS\n"
    "# lecteur backend. DETTE : ne peut que RETRECIR (--write-baseline refuse\n"
    "# d'ajouter).\n"
)


def _est_test(p: Path) -> bool:
    return ("tests" in p.parts or "__tests__" in p.parts or "migrations" in p.parts
            or ".test." in p.name or p.name.startswith(("test_", "tests_")))


def cles_entree(root: Path = ROOT) -> list:
    src = (root / ELECTRIQUE).read_text(encoding="utf-8")
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "CHAMPS_ENTREE" for t in n.targets):
            return [(f"entree::{e.value}", e.value, n.lineno, n.end_lineno)
                    for e in n.value.elts if isinstance(e, ast.Constant)]
    return []


def cles_registres(root: Path = ROOT) -> list:
    src = (root / PARAMETRES).read_text(encoding="utf-8")
    arbre = ast.parse(src)
    tuples = {}
    consts = {}
    for n in arbre.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            nom = n.targets[0].id
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                consts[nom] = n.value.value
            elif isinstance(n.value, ast.Tuple):
                tuples[nom] = [e.elts[0].value for e in n.value.elts
                               if isinstance(e, ast.Tuple) and e.elts
                               and isinstance(e.elts[0], ast.Constant)]
    out = []
    for n in arbre.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "REGISTRES" for t in n.targets):
            for k, v in zip(n.value.keys, n.value.values):
                section = consts.get(k.id) if isinstance(k, ast.Name) else getattr(k, "value", None)
                if isinstance(v, ast.Name) and section:
                    for cle in tuples.get(v.id, []):
                        out.append((f"registre::{section}.{cle}", cle, 0, 0))
    return out


def _textes_backend(root: Path) -> dict:
    """{fichier relatif: lignes} du code backend calepinage (hors tests)."""
    out = {}
    for p in sorted((root / BACKEND).rglob("*.py")):
        rel = p.relative_to(root)
        if _est_test(rel.relative_to(BACKEND)) or rel == PARAMETRES:
            continue
        out[rel] = p.read_text(encoding="utf-8").splitlines()
    for p in sorted((root / LECTEURS_CORE).rglob("*.py")):
        rel = p.relative_to(root)
        if not _est_test(rel.relative_to(LECTEURS_CORE)):
            out[rel] = p.read_text(encoding="utf-8").splitlines()
    return out


def _texte_backend(textes: dict, masque: tuple | None) -> str:
    """Concaténation, en blanchissant les lignes ``masque`` = (fichier, début,
    fin) de la déclaration de la clé."""
    morceaux = []
    for rel, lignes in textes.items():
        if masque and rel == masque[0]:
            lignes = list(lignes)
            for i in range(masque[1] - 1, masque[2]):
                lignes[i] = ""
        morceaux.append(chr(10).join(lignes))
    return chr(10).join(morceaux)


def _texte_front(root: Path) -> str:
    morceaux = []
    api = root / FRONT_API
    if api.is_file():
        morceaux.append(api.read_text(encoding="utf-8"))
    for p in sorted((root / FRONT_FEATURES).rglob("*")):
        if p.suffix in (".js", ".jsx") and not _est_test(p.relative_to(root)):
            morceaux.append(p.read_text(encoding="utf-8"))
    return "\n".join(morceaux)


def _sans_commentaires_js(texte: str) -> str:
    """Retire les commentaires `/* … */` et `// …` (précédé d'un blanc ou en
    début de ligne, pour épargner `https://` dans une chaîne)."""
    texte = re.sub(r"/\*.*?\*/", " ", texte, flags=re.S)
    return re.sub(r"(^|[ \t])//[^\n]*", r"\1", texte, flags=re.M)


def _texte_atelier(root: Path) -> str:
    """Sources de l'atelier de toiture (+ relais), hors tests, sans commentaires."""
    fichiers = []
    for base in ATELIER_SOURCES:
        if (root / base).is_dir():
            fichiers += sorted(p for p in (root / base).rglob("*")
                               if p.is_file() and p.suffix in (".ts", ".js"))
    if (root / ATELIER_RELAIS).is_file():
        fichiers.append(root / ATELIER_RELAIS)
    morceaux = [_sans_commentaires_js(p.read_text(encoding="utf-8")) for p in fichiers
                if not _est_test(p.relative_to(root))]
    return "\n".join(morceaux)


def _lu_par_atelier(cle: str, texte: str) -> bool:
    """Vrai si la clé est LUE par son nom : `.cle`, `?.cle` ou `['cle']`."""
    c = re.escape(cle)
    motif = r"\.\s*" + c + r"(?![\w])|\[\s*['\"`]" + c + r"['\"`]\s*\]"
    return re.search(motif, texte) is not None


def _present(cle: str, texte: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(cle) + r"(?![\w])", texte) is not None


def plage_entree(root: Path) -> tuple:
    cles = cles_entree(root)
    return (cles[0][2], cles[0][3]) if cles else (1, 0)


def analyser(root: Path = ROOT) -> set:
    """Ensemble des clés de dette ``<id>::ecran`` / ``<id>::lecteur``."""
    front = _texte_front(root)
    atelier = _texte_atelier(root)
    textes = _textes_backend(root)
    sans_masque = _texte_backend(textes, None)
    avec_masque = _texte_backend(textes, (ELECTRIQUE, *plage_entree(root)))
    dettes = set()
    for ident, cle, debut, fin in cles_entree(root) + cles_registres(root):
        if ident in EXCEPTEES:
            continue
        corpus = avec_masque if ident.startswith("entree::") else sans_masque
        lecteur_serveur = _present(cle, corpus)
        lecteur_atelier = ident.startswith("registre::") and _lu_par_atelier(cle, atelier)
        if not (lecteur_serveur or lecteur_atelier):
            dettes.add(f"{ident}::lecteur")
        if ident.startswith("entree::") and not _present(cle, front):
            dettes.add(f"{ident}::ecran")
    return dettes


def decrire(cle: str) -> str:
    ident, manque = cle.rsplit("::", 1)
    if manque == "ecran":
        return (f"{ident.split('::', 1)[1]} : clé admise par le serveur sans ÉCRIVAIN "
                "d'écran (calepinageApi.js / features/calepinage).")
    if ident.startswith("registre::"):
        return (f"{ident.split('::', 1)[1]} : clé admise par le serveur sans lecteur, ni côté "
                "serveur (aucun lecteur serveur : calepinage / core/electrique) ni dans l'atelier "
                "(aucun lecteur atelier : accès par son nom dans roofPro11 / lib / useAtelierBoot.js) "
                "— rien ne la consomme.")
    return (f"{ident.split('::', 1)[1]} : clé admise par le serveur sans lecteur serveur "
            "(rien ne la consomme ; l'atelier ne compte que pour les réglages).")


def verifier(dettes: set, base: set) -> list:
    return _cliquet.comparer(dettes, base, nom_fichier="saisies_electriques_allow.txt",
                             decrire=decrire)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--autoriser-croissance", action="store_true")
    args = ap.parse_args(argv)
    dettes = analyser()
    if args.write_baseline:
        try:
            _cliquet.ecrire(BASELINE, dettes, ENTETE, "ACAL322 saisie non branchée",
                            autoriser_croissance=args.autoriser_croissance)
        except ValueError as exc:
            print("REFUS : " + str(exc))
            return 1
        print(f"Base réécrite ({len(dettes)} entrée(s)).")
        return 0
    erreurs = verifier(dettes, _cliquet.charger(BASELINE))
    if erreurs:
        print("check_saisies_electriques_branchees: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_saisies_electriques_branchees: OK — {len(dettes)} dette(s) gelée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
