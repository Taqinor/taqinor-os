#!/usr/bin/env python3
"""GARDE C20 (stage-names) — la forme du code, jugee sur le DIFF seul (AMET85, C-AMET-023).

Mesure du 09/10/2026 : +17 % de code en 7 j, 523 facades F401, 4 176 entrees gelees.
Compare `merge-base(--base, --tete)` a `--tete` (commits) ; ne lit JAMAIS une baseline.
Regles (une par module de `scripts/forme_code/`) : FICHIER_MUR (>= 2 000 lignes :
lignes logiques nettes <= `lignes nettes attendues ≤ N` des taches cochees citant le
chemin EXACT), FONCTION_NEUVE (<= 60), FONCTION_MUR (> 100 ne grossit pas), FACADE
(noms neufs `# noqa: F401` / alias), REGLAGE (settings + .env.example), GARDE_NEUVE,
BASELINE_GROSSIT, deplacement SPL (empreinte AST), EXCEPTION (`Exception C20 : <REGLE>
<chemin> car :` sur une tache cochee). Ailleurs : test nomme par id -> check_test_placement
(AMET84) ; helper jumeau -> check_duplicats_litteraux ; cle de ligne -> AMET100.
Clone superficiel ou base introuvable : ECHEC (« garde inoperante »), jamais un vert.
PR de revert (TOUS ses commits non-merge `merge-base..tete` sont des `git revert`) : non jugee,
exit 0 — `main` reste toujours revertable (CLAUDE.md) ; une PR mixte est jugee normalement.

Usage :
    python scripts/check_forme_code.py [--base origin/main] [--tete HEAD]
    python scripts/check_forme_code.py --inspecter <fichier::symbole>   (audit_tache.inspecter)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from forme_code import (baseline_grossit, deplacement, exception, facade, fichier_mur,  # noqa: E402
                        fonction_mur, fonction_neuve, garde_neuve, reglage)
from forme_code.socle import Contexte, Echec, git  # noqa: E402

REGLES = (fichier_mur, fonction_neuve, fonction_mur, facade, reglage, garde_neuve, baseline_grossit)
INOPERANTE = "clone superficiel : garde inopérante"
REVERT = 'Revert "'


def _sha(racine, ref: str) -> str | None:
    try:
        return git(racine, "rev-parse", "--verify", "--quiet", ref + "^{commit}").decode().strip()
    except Echec:
        return None


def resoudre_base(racine, base: str, tete: str) -> tuple:
    """(merge-base, sha tete) — echoue ferme si l'historique ne permet pas de juger."""
    if _sha(racine, base) is None and os.environ.get("GITHUB_ACTIONS") and base == "origin/main":
        try:
            git(racine, "fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
        except Echec as exc:
            print(f"fetch de {base} impossible : {exc}", file=sys.stderr)
    sha_base, sha_tete = _sha(racine, base), _sha(racine, tete)
    if sha_base is None or sha_tete is None:
        raise Echec(f"{INOPERANTE} (référence {base if sha_base is None else tete} introuvable)")
    if git(racine, "rev-parse", "--is-shallow-repository").decode().strip() == "true":
        raise Echec(f"{INOPERANTE} (dépôt shallow : fetch-depth: 0 requis)")
    try:
        return git(racine, "merge-base", sha_base, sha_tete).decode().strip(), sha_tete
    except Echec:
        raise Echec(f"{INOPERANTE} (aucune base commune entre {base} et {tete})") from None


def est_pr_de_revert(racine, mb: str, tete: str) -> bool:
    """Vrai si les commits non-merge `mb..tete` sont TOUS des `git revert` (revenir en arriere reste permis)."""
    brut = git(racine, "log", "--no-merges", "--format=%s", f"{mb}..{tete}").decode("utf-8", "replace")
    sujets = [s for s in brut.splitlines() if s.strip()]
    return bool(sujets) and all(s.startswith(REVERT) for s in sujets)


def analyser(racine, base: str, tete: str) -> dict:
    """API (rejouer_prs, AMET87) : juge le diff `base..tete` entre deux commits."""
    ctx = Contexte(racine, base, tete)
    ctx.deplaces = deplacement.verifier(ctx)
    constats = [c for regle in REGLES for c in regle.verifier(ctx)]
    restants, exemptes, inutiles = exception.verifier(ctx, constats)
    return {"constats": restants, "exemptes": exemptes, "inutiles": inutiles, "taches": ctx.taches,
            "fichiers": len(ctx.changements), "deplaces": len(ctx.deplaces.entres)}


def rapport(r: dict, base: str, mb: str, tete: str) -> str:
    ids = ", ".join(i for i, _ in r["taches"]) or "aucune"
    lignes = [f"check_forme_code : {base} (merge-base {mb[:9]}) → {tete[:9]} : {r['fichiers']} fichier(s), "
              f"{r['deplaces']} symbole(s) déplacé(s), tâche(s) cochée(s) : {ids}"]
    for ident, constats in sorted(r["exemptes"].items()):
        lignes.append(f"  exception C20 de {ident} : {len(constats)} constat(s) exempté(s) — "
                      + " ; ".join(f"{c.regle} {c.cible()}" for c in constats))
    lignes += [f"  exception C20 sans effet : {e}" for e in r["inutiles"]]
    if not r["constats"]:
        return "\n".join(lignes + ["check_forme_code : OK — forme du code conforme (C20)."])
    lignes.append(f"check_forme_code : ÉCHEC — {len(r['constats'])} constat(s) C20")
    lignes += [f"  - [{c.regle}] {c.cible()} : {c.message}" for c in r["constats"]]
    return "\n".join(lignes)


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        getattr(flux, "reconfigure", lambda **_: None)(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Garde C20 : forme du code sur le diff (AMET85).")
    parser.add_argument("--base", default="origin/main", help="référence de base (merge-base avec --tete)")
    parser.add_argument("--tete", default="HEAD", help="commit jugé (défaut HEAD)")
    parser.add_argument("--inspecter", metavar="FICHIER::SYMBOLE", help="emplacement, jumeaux, test canonique")
    parser.add_argument("--racine", default=str(ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.inspecter:
        import audit_tache
        print(audit_tache.inspecter(args.inspecter, args.racine)["texte"])
        return 0
    try:
        mb, tete = resoudre_base(args.racine, args.base, args.tete)
        if est_pr_de_revert(args.racine, mb, tete):
            print("check_forme_code : PR de revert : forme du code non jugée (main toujours revertable)")
            return 0
        resultat = analyser(args.racine, mb, tete)
    except Echec as exc:
        print(f"check_forme_code : ÉCHEC — {exc}")
        return 1
    print(rapport(resultat, args.base, mb, tete))
    return 1 if resultat["constats"] else 0


if __name__ == "__main__":
    sys.exit(main())
