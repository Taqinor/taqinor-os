#!/usr/bin/env python3
"""CI-5MIN (décision fondateur, 24/10/2026) — la merge queue réutilise le vert d'une PR.

POURQUOI. Chaque entrée de la merge queue rejouait le gate complet de `ci.yml`
(mesuré : 12,4 min réels, run 40034106320) alors que, pour une PR à jour avec
`main` seule dans son groupe, le commit du groupe porte EXACTEMENT le même arbre
que la tête de la PR, déjà testée verte. GitHub ne sait pas reporter les checks
d'une PR sur `merge_group` : ce script fait la preuve à sa place.

LA PREUVE (tout ou rien — le moindre doute rend « pas de réutilisation ») :
  1. le numéro de PR se lit dans `merge_group.head_ref`
     (`refs/heads/gh-readonly-queue/main/pr-<n>-<sha>`) ;
  2. l'arbre (tree SHA) de la tête de cette PR est IDENTIQUE à celui du commit
     du groupe — même code au fichier près ; un groupe à plusieurs PR ou une PR
     en retard sur `main` a un autre arbre et rejoue tout ;
  3. un run `ci.yml` déclenché par `pull_request` sur cette tête a conclu
     `success` (dernière tentative) ;
  4. ce run a fait tourner AU MOINS les surfaces que le groupe ferait tourner :
     on relit la ligne « Resolved -> … » et la portée du fuzz PR dans le
     journal de son job `changes` ; chaque surface vraie du groupe doit y être
     vraie, chaque paquet fuzzé par le groupe doit y avoir été fuzzé.

Sortie : l'identifiant du run réutilisé sur stdout, ou rien. Les raisons vont
sur stderr. Le script ne fait JAMAIS échouer le job : toute erreur (API, réseau,
journal illisible) = pas de réutilisation = le gate complet tourne, comme avant.

Stdlib pure + la CLI `gh` (présente sur les runners GitHub, GH_TOKEN fourni par
le job `changes`, permissions `actions: read` et `pull-requests: read`).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

SURFACES = ("backend", "frontend", "web", "yanbow", "fastapi", "code")

_PR_RE = re.compile(r"/pr-(\d+)-[0-9a-f]+$")
# « Resolved -> backend=true frontend=false … e2e(code)=true » : le `\)?`
# avale la parenthèse de `e2e(code)`, la clé lue est donc `code`.
_RESOLVED_RE = re.compile(r"(\w+)\)?=(true|false)")
_FUZZ_RE = re.compile(r"\(fuzz PR\) : (.*)$")


def numero_pr(head_ref: str) -> int | None:
    m = _PR_RE.search(head_ref.strip())
    return int(m.group(1)) if m else None


def est_allege(journal: str) -> bool:
    """CI-UNE (fondateur, 27/10/2026) — vrai si le job `changes` du run PR a
    tourné en mode allégé (`pull_request` sur une branche `claude/*`) : ses lanes
    lourdes ont été reportées au `merge_group`, son vert ne vaut donc PAS gate.
    Les lignes recopiées du script (`$`) sont ignorées comme ailleurs."""
    return any("allege=true" in ligne for ligne in journal.splitlines() if "$" not in ligne)


def lire_journal_changes(journal: str):
    """(surfaces, paquets fuzzés) relus dans le journal du job `changes`, ou None.

    Le journal recopie d'abord le script de l'étape (en-tête « Run … ») : ses
    `echo "… $backend …"` littéraux sont ignorés (pas de true/false, ou un `$`) ;
    les vraies lignes viennent après et l'emportent."""
    surfaces = None
    fuzz = None
    for ligne in journal.splitlines():
        if "$" in ligne:
            continue
        if "Resolved -> " in ligne:
            paires = dict(_RESOLVED_RE.findall(ligne.split("Resolved -> ", 1)[1]))
            if all(s in paires for s in SURFACES):
                surfaces = {s: paires[s] == "true" for s in SURFACES}
        m = _FUZZ_RE.search(ligne)
        if m:
            valeur = m.group(1).strip()
            fuzz = set() if valeur == "aucun" else set(valeur.split())
    if surfaces is None or fuzz is None:
        return None
    return surfaces, fuzz


def couvre(groupe: dict, fuzz_groupe: set, pr: dict, fuzz_pr: set) -> list[str]:
    """Liste des manques (vide = le run PR couvre tout ce que le groupe ferait)."""
    manques = [f"surface {s}" for s in SURFACES if groupe.get(s) and not pr.get(s)]
    manques += [f"fuzz {p}" for p in sorted(fuzz_groupe - fuzz_pr)]
    return manques


def lire_drapeaux(texte: str) -> dict:
    paires = dict(re.findall(r"(\w+)=(true|false)", texte))
    return {s: paires.get(s) == "true" for s in SURFACES}


def _gh(*args: str) -> str:
    return subprocess.run(["gh", "api", *args], check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _journal(repo: str, job: str) -> str:
    """Journal d'un job. Il contient des séquences de couleur : sans
    `--allow-escape-sequences`, `gh api` refuse de l'afficher (vu en local,
    gh 2.8x) ; une gh plus ancienne ne connaît pas l'option -> second essai."""
    url = f"repos/{repo}/actions/jobs/{job}/logs"
    try:
        texte = _gh(url, "--allow-escape-sequences")
    except subprocess.CalledProcessError:
        texte = _gh(url)
    return _ANSI_RE.sub("", texte)


def chercher(repo: str, head_ref: str, arbre_groupe: str, groupe: dict,
             fuzz_groupe: set) -> str | None:
    def non(raison: str):
        print(f"Merge queue : pas de réutilisation — {raison}.", file=sys.stderr)
        return None

    n = numero_pr(head_ref)
    if n is None:
        return non(f"head_ref illisible ({head_ref!r})")
    tete = _gh(f"repos/{repo}/pulls/{n}", "--jq", ".head.sha").strip()
    arbre_pr = _gh(f"repos/{repo}/git/commits/{tete}", "--jq", ".tree.sha").strip()
    if not arbre_pr or arbre_pr != arbre_groupe:
        return non(f"arbre de la PR #{n} ({arbre_pr[:12]}) différent du groupe "
                   f"({arbre_groupe[:12]}) — PR en retard ou groupe à plusieurs PR")
    runs = _gh(f"repos/{repo}/actions/workflows/ci.yml/runs?head_sha={tete}"
               "&event=pull_request&status=success&per_page=10",
               "--jq", ".workflow_runs[].id").split()
    for run in runs:
        job = _gh(f"repos/{repo}/actions/runs/{run}/jobs?per_page=100", "--jq",
                  '.jobs[] | select(.name == "changes") | .id').split()
        if not job:
            continue
        texte = _journal(repo, job[0])
        if est_allege(texte):
            print(f"Merge queue : run {run} allégé (CI-UNE : lanes lourdes reportées au "
                  "groupe) — ne vaut pas gate.", file=sys.stderr)
            continue
        lu = lire_journal_changes(texte)
        if lu is None:
            print(f"Merge queue : run {run}, journal `changes` illisible.", file=sys.stderr)
            continue
        manques = couvre(groupe, fuzz_groupe, *lu)
        if manques:
            print(f"Merge queue : run {run} ne couvre pas {', '.join(manques)}.",
                  file=sys.stderr)
            continue
        print(f"Merge queue : arbre identique à la PR #{n} ({tete[:12]}), run PR vert "
              f"{run} couvrant toutes les surfaces du groupe.", file=sys.stderr)
        return run
    return non(f"aucun run PR vert de ci.yml sur la tête {tete[:12]} qui couvre le groupe")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", required=True)
    p.add_argument("--head-ref", required=True)
    p.add_argument("--group-tree", required=True)
    p.add_argument("--flags", required=True, help='"backend=true frontend=false …"')
    p.add_argument("--fuzz", default="", help="paquets d'API du groupe, séparés par des espaces")
    a = p.parse_args(argv)
    try:
        run = chercher(a.repo, a.head_ref, a.group_tree.strip(),
                       lire_drapeaux(a.flags), set(a.fuzz.split()))
    except Exception as exc:  # noqa: BLE001 — tout doute = gate complet
        print(f"Merge queue : pas de réutilisation — erreur {exc!r}.", file=sys.stderr)
        run = None
    if run:
        print(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
