#!/usr/bin/env python3
"""PACT12 — une tache MIXTE compte pour DEUX moities : une seule livree, elle
reste `[ ]`.

POURQUOI CETTE GARDE EXISTE
---------------------------
En juillet 2026, ``docs/FRONTEND_GAP_PLAN.md`` a constate, noir sur blanc, que
« the paired frontend half of each task was never built, **EVEN THOUGH** most
tasks named a ``frontend/`` file in their own ``Files:`` line ». La ligne
``Files:`` ANNONCAIT deja les deux moities — et rien, ni CI ni harnais, ne
verifiait qu'elles avaient ete touchees TOUTES LES DEUX. 147 taches ont ete
ecrites pour rattraper le manque ; 145 sont encore ouvertes un mois plus tard.

Cocher `[x]` une tache mixte a moitie livree n'est pas une erreur d'agent :
c'est un controle qui n'existait pas. Le voici.

LA REGLE
--------
Une tache est MIXTE quand sa ligne ``Files:`` nomme AU MOINS un chemin
``backend/`` ET au moins un chemin ``frontend/``. Une tache mixte cochee `[x]`
doit avoir les deux moities REELLEMENT presentes.

DEUX CONTROLES, DELIBEREMENT DIFFERENTS
---------------------------------------
1. **Existence sur disque (par defaut, sans git).** Un fichier declare qui
   N'EXISTE PAS prouve que cette moitie n'a pas ete construite. C'est exact,
   ca marche dans n'importe quel clone (le job CI `stage-names` est un clone
   superficiel : aucune base de comparaison git n'y est disponible), et ca ne
   peut pas produire de faux positif : soit le fichier est la, soit il ne
   l'est pas.

   LIMITE ASSUMEE : un fichier qui existait DEJA et que la tache devait
   modifier passe ce controle. Sous-detecter est le comportement voulu — une
   garde qui crie au loup finit desactivee.

2. **Diff de branche (`--base <ref>`, optionnel).** Quand l'historique est
   disponible (local, ou un checkout `fetch-depth: 0`), on regarde ce que la
   branche a REELLEMENT touche : une tache qui passe de `[ ]` a `[x]` dans
   cette branche et dont le diff ne touche qu'un cote est refusee, en NOMMANT
   le cote manquant. C'est le controle complet ; il n'est simplement pas
   disponible partout.

BASE DE REFERENCE — ELLE NE PEUT QUE RETRECIR
---------------------------------------------
La dette historique est figee dans ``scripts/plan_taches_mixtes_allow.txt``.
Seule une occurrence NOUVELLE echoue. ``--write-baseline`` REFUSE d'ajouter une
ligne ; assumer une dette exige ``--autoriser-croissance`` (fondateur, visible
en revue).

Usage :
    python scripts/check_plan_taches_mixtes.py
    python scripts/check_plan_taches_mixtes.py --stats
    python scripts/check_plan_taches_mixtes.py --base origin/main
    python scripts/check_plan_taches_mixtes.py --write-baseline
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "scripts" / "plan_taches_mixtes_allow.txt"


def fichiers_de_plan(racine: Path = None) -> list[Path]:
    """Fichiers de plan balayes : tout `docs/PLAN*.md` sauf le mode d'emploi,
    plus les files de domaine `docs/plans/PLAN_*.md` et le backlog NT."""
    racine = ROOT if racine is None else racine
    docs = racine / "docs"
    if not docs.is_dir():
        return []
    trouves = {
        p for p in docs.glob("*PLAN*.md") if p.name != "PLAN_HOWTO.md"
    }
    trouves |= set((docs / "plans").glob("PLAN_*.md"))
    nt = docs / "new_tasks_plan.md"
    if nt.is_file():
        trouves.add(nt)
    return sorted(trouves)


# `- [x] ID — texte …` / `- [ ] ID — texte …`
# L'identifiant accepte le trait d'union et la barre oblique : les tâches de
# `docs/FRONTEND_GAP_PLAN.md` s'appellent `FE-XFLT4`, `FE-XFLT7/15/18`.
_TACHE_RE = re.compile(
    r"^\s*[-*]\s*\[(?P<etat>[^\]]*)\]\s*(?P<id>[A-Z][A-Z0-9]*(?:[-/][A-Z0-9]+)*\d[\w/-]*)"
    r"(?P<label>.*)$")
_FICHIER_RE = re.compile(r"[\w./-]+\.(?:py|jsx?|mjs|tsx?|css|html|txt|ya?ml|md)")


def _fichiers_declares(label: str) -> list[str]:
    """Les chemins de la DERNIERE clause `Files:` de la ligne."""
    idx = label.rfind("Files:")
    if idx < 0:
        idx = label.rfind("Files :")
    if idx < 0:
        return []
    return [raw.strip("`'\" ") for raw in _FICHIER_RE.findall(label[idx:])]


def _cote(chemin: str) -> str | None:
    if chemin.startswith("frontend/") or "/frontend/src/" in chemin:
        return "frontend"
    if chemin.startswith(("backend/", "apps/")) or "/backend/django_core/" in chemin:
        return "backend"
    return None


def taches_mixtes(fichiers=None):
    """[(fichier, ligne, id, cochee, {cote: [chemins]})] — toutes les mixtes."""
    out = []
    for chemin_plan in (fichiers_de_plan() if fichiers is None else fichiers):
        try:
            texte = chemin_plan.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for numero, ligne in enumerate(texte.splitlines(), 1):
            m = _TACHE_RE.match(ligne)
            if not m:
                continue
            par_cote: dict[str, list[str]] = {}
            for chemin in _fichiers_declares(m.group("label")):
                cote = _cote(chemin)
                if cote:
                    par_cote.setdefault(cote, []).append(chemin)
            if len(par_cote) < 2:
                continue
            out.append((chemin_plan, numero, m.group("id"),
                        m.group("etat").strip().lower() == "x", par_cote))
    return out


def _existe(chemin: str, racine: Path) -> bool:
    """Le chemin declare existe-t-il, quelle que soit sa racine ?

    Une tache ecrit indifferemment `apps/ao/urls.py` ou
    `backend/django_core/apps/ao/urls.py` : les deux designent le meme fichier.
    """
    candidats = [racine / chemin]
    if chemin.startswith("apps/"):
        candidats.append(racine / "backend" / "django_core" / chemin)
    if chemin.startswith("src/"):
        candidats.append(racine / "frontend" / chemin)
    return any(c.exists() for c in candidats)


def moities_absentes(racine: Path = None, fichiers=None):
    """[(signature, message)] — moities cochees dont le code n'existe pas."""
    racine = ROOT if racine is None else racine
    constats = []
    for chemin_plan, numero, tache, cochee, par_cote in taches_mixtes(fichiers):
        if not cochee:
            continue
        for cote, chemins in sorted(par_cote.items()):
            # Un cote n'est declare absent que si AUCUN de ses fichiers
            # n'existe : une tache qui nomme trois ecrans et n'en cree qu'un
            # a bien livre cette moitie.
            #
            # Les chemins terminant par `/` (un DOSSIER declare) sont ignores :
            # `_FICHIER_RE` ne les capture pas, donc la liste peut etre vide.
            if not chemins or any(_existe(c, racine) for c in chemins):
                continue
            autre = "frontend" if cote == "backend" else "backend"
            constats.append((
                f"{tache}|{cote}",
                f"{chemin_plan.name}:{numero}  {tache} est cochee [x] mais sa "
                f"moitie {cote.upper()} n'existe pas : "
                f"{', '.join(chemins)} — introuvable(s). "
                f"Seule la moitie {autre} a ete livree."))
    return constats


# ===========================================================================
# Controle complet : le DIFF de la branche (quand l'historique est la)
# ===========================================================================

def _git(*args, racine: Path = None):
    racine = ROOT if racine is None else racine
    try:
        proc = subprocess.run(["git", *args], cwd=str(racine),
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def moities_non_touchees(base: str, racine: Path = None):
    """[(signature, message)] — taches cochees DANS CETTE BRANCHE, un seul cote touche.

    Renvoie ``None`` (et non une liste vide) quand l'historique ne permet pas
    la comparaison : un clone superficiel ne doit JAMAIS produire un faux rouge.
    """
    racine = ROOT if racine is None else racine
    fusion = _git("merge-base", base, "HEAD", racine=racine)
    if not fusion:
        return None
    fusion = fusion.strip()
    touches = _git("diff", "--name-only", f"{fusion}...HEAD", racine=racine)
    if touches is None:
        return None
    touches = {ligne.strip() for ligne in touches.splitlines() if ligne.strip()}
    cotes_touches = {c for c in (_cote(t) for t in touches) if c}

    constats = []
    for chemin_plan, numero, tache, cochee, par_cote in taches_mixtes():
        if not cochee:
            continue
        relatif = chemin_plan.relative_to(racine).as_posix() \
            if chemin_plan.is_relative_to(racine) else chemin_plan.name
        avant = _git("show", f"{fusion}:{relatif}", racine=racine)
        if avant is None:
            continue        # fichier de plan nouveau : rien a comparer
        if not _etait_cochee(avant, tache):
            for cote in sorted(par_cote):
                if cote in cotes_touches:
                    continue
                autre = "frontend" if cote == "backend" else "backend"
                constats.append((
                    f"{tache}|{cote}",
                    f"{chemin_plan.name}:{numero}  {tache} passe a [x] dans "
                    f"cette branche, mais son diff ne touche AUCUN fichier "
                    f"{cote.upper()} — seule la moitie {autre} a ete livree "
                    f"(declare : {', '.join(par_cote[cote])})"))
    return constats


def _etait_cochee(texte: str, tache: str) -> bool:
    motif = re.compile(r"^\s*[-*]\s*\[\s*[xX]\s*\]\s*%s\b" % re.escape(tache),
                       re.MULTILINE)
    return bool(motif.search(texte))


# ===========================================================================
# Base de reference + CLI
# ===========================================================================

ENTETE_BASE = """\
# PACT12 — base de reference de check_plan_taches_mixtes.py : DETTE HISTORIQUE.
#
# Chaque ligne est `<ID de tache>|<cote manquant>` : une tache cochee [x] dont
# la ligne `Files:` annonce DEUX moities (backend ET frontend) alors qu'une
# seule a ete livree. C'est exactement le constat de docs/FRONTEND_GAP_PLAN.md
# en juillet 2026 : « the paired frontend half of each task was never built,
# EVEN THOUGH most tasks named a frontend/ file in their own Files: line ».
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - livrer la moitie manquante puis `--write-baseline` retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Assumer une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur.
#
# La signature est `ID|cote`, jamais `fichier:ligne` : un deplacement de ligne
# ne doit pas invalider la base (lecon du depot).
"""


def charger_base(path: Path = BASELINE_PATH) -> set[str]:
    if not path.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def ecrire_base(signatures, path: Path = BASELINE_PATH):
    path.write_text(ENTETE_BASE + "\n".join(sorted(signatures)) + "\n",
                    encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="PACT12 — une tache mixte livree a moitie ne peut pas etre cochee.")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--base", metavar="REF",
                        help="compare aussi le DIFF de la branche a cette base "
                             "(ex. origin/main) — ignore si l'historique manque")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    mixtes = taches_mixtes()
    constats = moities_absentes()
    par_diff = None
    if args.base:
        par_diff = moities_non_touchees(args.base)
        if par_diff is None:
            print(f"Info : historique insuffisant pour comparer a « {args.base} » "
                  f"(clone superficiel) — seul le controle d'existence tourne.")
        else:
            connues = {s for s, _ in constats}
            constats += [c for c in par_diff if c[0] not in connues]

    if args.stats:
        cochees = sum(1 for *_, cochee, _ in mixtes if cochee)
        print(f"Taches MIXTES (backend + frontend dans la meme ligne Files:) : "
              f"{len(mixtes)} ({cochees} cochees, {len(mixtes) - cochees} ouvertes).")
        print(f"Moities manquantes detectees : {len(constats)}.")

    base = charger_base()
    signatures = {s for s, _ in constats}

    if args.write_baseline:
        ajouts = signatures - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            for signature in sorted(ajouts)[:20]:
                print(f"  + {signature}")
            print("Livrez la moitie manquante, ou assumez la dette avec "
                  "--autoriser-croissance.")
            return 1
        ecrire_base(signatures)
        print(f"Base de reference reecrite : {BASELINE_PATH.relative_to(ROOT)} "
              f"({len(signatures)} entree(s), {len(base - signatures)} retiree(s)).")
        return 0

    nouveaux = sorted((s, m) for s, m in constats if s not in base)
    if nouveaux:
        print(f"\nECHEC : {len(nouveaux)} tache(s) mixte(s) cochee(s) [x] avec "
              f"UNE SEULE moitie livree.\n")
        for _, message in nouveaux:
            print(f"  {message}")
        print("\nUne ligne `Files:` qui nomme un fichier backend ET un fichier "
              "frontend ANNONCE deux moities.\nEn livrer une seule et cocher la "
              "tache, c'est exactement ce qu'a constate\n"
              "docs/FRONTEND_GAP_PLAN.md en juillet 2026 : 147 taches de "
              "rattrapage ecrites,\n145 encore ouvertes un mois plus tard.\n")
        print("CORRIGER : livrer la moitie manquante, ou remettre la tache a "
              "`[ ]` et retirer\nde sa ligne `Files:` le cote qui n'est pas de "
              "son ressort.")
        return 1

    corrigees = len(base - signatures)
    print(f"OK : {len(mixtes)} tache(s) mixte(s) lue(s), aucune moitie manquante "
          f"nouvelle ({len(base)} dette(s) historique(s), dont {corrigees} "
          f"desormais corrigee(s)).")
    if corrigees:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_plan_taches_mixtes.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
