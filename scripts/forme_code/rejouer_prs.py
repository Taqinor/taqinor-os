#!/usr/bin/env python3
"""Rejeu de check_forme_code sur les PR fusionnees (AMET87) : `git log --first-parent`, squash
COMPRIS (le rejeu R2_5 prenait `--merges` et sautait #890). Rapport par classe : compte, 10 exemples
(graine fixe), precision a remplir par relecture ; exit 1 si une analyse plante. Jamais une baseline.

    python scripts/forme_code/rejouer_prs.py [--n 100] [--graine 11] [--ref origin/main] [--sortie f.md]
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_forme_code as cfc  # noqa: E402
from forme_code.socle import git  # noqa: E402

CLASSES = ("FICHIER_MUR", "FONCTION_NEUVE", "FONCTION_MUR", "FACADE", "REGLAGE", "GARDE_NEUVE",
           "BASELINE_GROSSIT", "CLE_LIGNE", "EXCEPTION")


def commits_fusionnes(racine, ref: str, n: int) -> list:
    """[(sha, premier parent, sujet)] des `n` derniers commits de `ref` en --first-parent (squash compris)."""
    sortie = git(racine, "log", "--first-parent", f"-n{n}", "--format=%H %P%x09%s", ref).decode("utf-8", "replace")
    commits = []
    for ligne in sortie.splitlines():
        shas, _, sujet = ligne.partition("\t")
        parties = shas.split()
        if len(parties) >= 2:
            commits.append((parties[0], parties[1], sujet))
    return commits


def rejouer(racine, ref: str, n: int, journal=sys.stderr) -> dict:
    par_classe = {c: [] for c in CLASSES}
    durees, plantages = [], []
    commits = commits_fusionnes(racine, ref, n)
    for i, (sha, parent, sujet) in enumerate(commits, 1):
        debut = time.perf_counter()
        try:
            r = cfc.analyser(racine, parent, sha)
        except Exception as exc:  # le rejeu MESURE les plantages : aucun n'est tolere
            plantages.append(f"{sha[:9]} {sujet} : {type(exc).__name__}: {exc}")
            continue
        finally:
            durees.append(time.perf_counter() - debut)
        pr = f"{sha[:9]} {sujet[:60]}"
        for c in r["constats"]:
            par_classe[c.regle].append((pr, f"{c.cible()} : {c.message}"))
        for ident, exemptes in r["exemptes"].items():
            par_classe["EXCEPTION"] += [(pr, f"{ident} exempte {c.regle} {c.cible()}") for c in exemptes]
        print(f"[rejeu] {i}/{len(commits)} {pr} : {len(r['constats'])} constat(s) en {durees[-1]:.1f} s",
              file=journal)
    return {"par_classe": par_classe, "durees": durees, "plantages": plantages, "commits": len(commits)}


def rapport(res: dict, graine: int) -> str:
    durees = res["durees"] or [0.0]
    lignes = [f"# Rejeu check_forme_code — {res['commits']} PR (--first-parent, squash compris), graine {graine}", "",
              f"Médiane {statistics.median(durees):.2f} s / PR, max {max(durees):.2f} s ; "
              f"plantages Python : {len(res['plantages'])}", "",
              "| classe | constats | précision (relue, x/10) |", "|---|---|---|"]
    lignes += [f"| {c} | {len(v)} | à remplir |" for c, v in res["par_classe"].items()]
    tirage = random.Random(graine)
    for classe, constats in res["par_classe"].items():
        if constats:
            lignes += ["", f"## {classe} — {len(constats)} constat(s), 10 exemples", ""]
            lignes += [f"- `{pr}` — {texte}" for pr, texte in tirage.sample(constats, min(10, len(constats)))]
    lignes += [f"- PLANTAGE {p}" for p in res["plantages"]]
    return "\n".join(lignes) + "\n"


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        getattr(flux, "reconfigure", lambda **_: None)(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Rejeu de check_forme_code sur les PR fusionnées (AMET87).")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--graine", type=int, default=11)
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--sortie", help="fichier Markdown (défaut : sortie standard)")
    parser.add_argument("--racine", default=str(cfc.ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    res = rejouer(args.racine, args.ref, args.n)
    texte = rapport(res, args.graine)
    if args.sortie:
        Path(args.sortie).write_text(texte, encoding="utf-8")
    print(texte if not args.sortie else texte.split("\n\n## ")[0])
    return 1 if res["plantages"] else 0


if __name__ == "__main__":
    sys.exit(main())
