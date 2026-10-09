#!/usr/bin/env python3
"""GARDE CI (stage-names) — ACAL343 : le document de référence porte TOUTES les clés.

CLASSE C-ACAL-045/131/146 : une clé racine ajoutée au schéma `roof_layout_v2`
sans entrée dans `exemple` (le document de référence du test d'aller-retour)
ou sans AUCUN écrivain est perdue au prochain « Enregistrer ». La garde lit
`apps/calepinage/contract_samples/roof_layout_v2.schema.json` et échoue en
nommant la clé si :

  (a) une clé racine de `properties` manque à `exemple`  -> `exemple::<clé>` ;
  (b) une clé racine n'a aucun écrivain : ni `serializeLayout` / `prefill.ts`
      / un onglet de `frontend/src/features/calepinage`, ni un service
      d'`apps/calepinage` qui la nomme                      -> `ecrivain::<clé>`.

Les écrivains sont reconnus par REGEX d'identifiant de clé (mot entier) dans
les sources réelles ; la sortie dit combien de sources ont été lues.
Passif gelé : `scripts/cles_document_sans_ecrivain_allow.txt` (clés
`exemple::…` / `ecrivain::…`), ne peut que RÉTRÉCIR (`--write-baseline` refuse
d'ajouter) ; une clé morte fait échouer la garde.

Usage :
    python scripts/check_calepinage_cles_document.py [--write-baseline]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cliquet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (Path("backend") / "django_core" / "apps" / "calepinage"
          / "contract_samples" / "roof_layout_v2.schema.json")
BASELINE = ROOT / "scripts" / "cles_document_sans_ecrivain_allow.txt"
SOURCES_FRONT = (
    (Path("frontend") / "src" / "features" / "calepinage", (".js", ".jsx", ".ts", ".tsx")),
    (Path("frontend") / "src" / "pages" / "ventes", (".js", ".jsx")),
    (Path("apps") / "web" / "src" / "scripts", (".ts",)),
)
SOURCES_BACK = (Path("backend") / "django_core" / "apps" / "calepinage" / "services",)
ENTETE = (
    "# Base de reference de check_calepinage_cles_document.py (ACAL343).\n"
    "# `exemple::<cle>` = cle racine du schema absente de `exemple` ;\n"
    "# `ecrivain::<cle>` = cle racine sans aucun ecrivain. DETTE : ne peut que\n"
    "# RETRECIR (--write-baseline refuse d'ajouter).\n"
)


def _est_test(p: Path) -> bool:
    return (".test." in p.name or "__tests__" in p.parts or "tests" in p.parts
            or p.name.startswith(("test_", "tests_")))


def lire_schema(root: Path = ROOT) -> tuple:
    doc = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
    return list(doc.get("properties", {})), doc.get("exemple") or {}


def corpus_ecrivains(root: Path = ROOT) -> tuple:
    """(texte concaténé, nombre de fichiers lus)."""
    morceaux, n = [], 0
    dossiers = [(d, exts) for d, exts in SOURCES_FRONT]
    dossiers += [(d, (".py",)) for d in SOURCES_BACK]
    for dossier, exts in dossiers:
        base = root / dossier
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.suffix in exts and not _est_test(p.relative_to(root)):
                try:
                    morceaux.append(p.read_text(encoding="utf-8"))
                    n += 1
                except (OSError, UnicodeDecodeError):
                    continue
    return chr(10).join(morceaux), n


def analyser(root: Path = ROOT) -> tuple:
    """(ensemble de dettes, nombre de sources lues)."""
    cles, exemple = lire_schema(root)
    texte, n = corpus_ecrivains(root)
    dettes = set()
    for cle in cles:
        if cle not in exemple:
            dettes.add(f"exemple::{cle}")
        c = re.escape(cle)
        # clé de document : chaîne littérale, propriété (`.clé`), clé d'objet
        # (`clé:`), affectation ou paramètre déstructuré — jamais un mot de prose.
        if not re.search(r"""['"]%s['"]|\.%s\b|(?<![\w])%s\s*[:=,}]""" % (c, c, c), texte):
            dettes.add(f"ecrivain::{cle}")
    return dettes, n


def decrire(cle: str) -> str:
    genre, nom = cle.split("::", 1)
    if genre == "exemple":
        return (f"clé racine '{nom}' du schéma absente de `exemple` (le document "
                "de référence du test d'aller-retour) — ajoutez-la à `exemple`.")
    return (f"clé racine '{nom}' sans AUCUN écrivain (serializeLayout / prefill.ts "
            "/ onglet calepinage / service) — elle serait perdue à l'enregistrement.")


def verifier(dettes: set, base: set) -> list:
    return _cliquet.comparer(dettes, base,
                             nom_fichier="cles_document_sans_ecrivain_allow.txt",
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
    dettes, n = analyser()
    if args.write_baseline:
        try:
            _cliquet.ecrire(BASELINE, dettes, ENTETE, "ACAL343 dette du jour",
                            autoriser_croissance=args.autoriser_croissance)
        except ValueError as exc:
            print("REFUS : " + str(exc))
            return 1
        print(f"Base réécrite ({len(dettes)} entrée(s)).")
        return 0
    erreurs = verifier(dettes, _cliquet.charger(BASELINE))
    if erreurs:
        print(f"check_calepinage_cles_document: ÉCHEC ({n} source(s) lue(s))")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_calepinage_cles_document: OK — {n} source(s) lue(s), "
          f"{len(dettes)} dette(s) gelée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
