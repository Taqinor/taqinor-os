#!/usr/bin/env python3
"""GARDE de placement des tests (AMET84, C-AMET-022) — jugee sur le DIFF de la PR, sans baseline.

Mesure du 09/10/2026 : 31/48 taches d'audit ont cree un fichier de test PAR TACHE ; 2 116 des
5 401 fichiers de test (39 %) portent un id de tache ; +1 162 fichiers en 7 jours.
Pour chaque fichier de test NOUVEAU (`A`, copie, ou renommage vers un autre nom) du diff
`merge-base(--base, --tete)..--tete` :
  1. un chemin cite par une tache v2 GELEE (`scripts/taches_audit_v2.txt`) que la PR coche
     -> AVERTISSEMENT, exit 0 (le chemin etait dicte avant la bascule v3) ;
  2. un nom qui porte un id de tache (`test_amet9_x.py`, `x.amet9.test.mjs`) -> ECHEC ; « id de
     tache » = `<prefixe><chiffres>` dont le prefixe est un VRAI prefixe de tache lu dans les plans
     a la tete (`- [ ]`/`[x]`/`[BLOCKED…]`/`[GATED…]` + registre `PREFIXE=N` de done_task.md) :
     `test_sha256_x.py`, `test_utf8_x.py`, `test_oauth2_x.py` n'en portent pas ;
  3. sinon ACCEPTE seulement si une ligne de tache cochee par la PR porte
     « Nouveau fichier car : » ET cite ce chemin (entre backticks) -> sinon ECHEC.
Un test ajoute a un module existant n'est jamais concerne. Clone superficiel ou base
introuvable : ECHEC (« garde inoperante »), jamais un vert — memes helpers que check_forme_code.

Usage : python scripts/check_test_placement.py [--base origin/main] [--tete HEAD]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_forme_code as cfc  # noqa: E402
from check_taches_cablage import charger_ids_v2  # noqa: E402
from forme_code.socle import Contexte, Echec, alias, lire_blobs  # noqa: E402

TYPE_DE_CLE = "par_symbole"  # sans objet : aucune baseline, la garde juge le diff seul
NOM_TEST = re.compile(r"^(?:tests?_.+|.+_test)\.py$|^tests\.py$|\.(?:test|spec)\.[cm]?[jt]sx?$", re.I)
NOM_AVEC_ID = re.compile(r"(?:^|[/\\])tests?_([a-z]{2,6})[0-9]{1,4}_|\.([a-z]{2,6})[0-9]{1,4}\.test\.", re.I)
PLAN_DE_TACHES = re.compile(r"^docs/(?:plans/[^/]+|PLAN[^/]*|[^/]*_PLAN[^/]*|new_tasks_plan|done_task)\.md$")
PREFIXE_TACHE = re.compile(r"^- \[(?:[ xX]|(?:BLOCKED|GATED)[^\]\n]*)\]\s*\**([A-Z]+)[0-9]+|^([A-Z]+)=[0-9]+[ \t]*$",
                           re.M)
NOUVEAU_FICHIER = re.compile(r"nouveau\s+fichier\s+car\s*:", re.I)
NOUVEAU_DOSSIER = re.compile(r"nouveau\s+dossier\s+car\s*:", re.I)
CHEMIN_CITE = re.compile(r"`([\w./-]+/[\w.-]+)(?:`|::)")


def est_fichier_test(chemin: str) -> bool:
    """Un module de test (par son NOM) — ni helper, ni fixture, ni `__init__`."""
    nom = chemin.rsplit("/", 1)[-1]
    return bool(NOM_TEST.search(nom)) and "node_modules/" not in chemin


def prefixes_de(texte: str) -> set:
    """Prefixes (minuscules) des ids de taches d'un plan, et du registre `PREFIXE=N` de done_task.md."""
    return {(tache or registre).lower() for tache, registre in PREFIXE_TACHE.findall(texte)}


def prefixes_connus(ctx) -> set:
    """Prefixes de taches REELS, lus dans les plans de la tete (une passe `git cat-file --batch`)."""
    plans = sorted(p for p in ctx.arbre_tete() if PLAN_DE_TACHES.match(p))
    textes = lire_blobs(ctx.racine, [f"{ctx.tete}:{p}" for p in plans]).values()
    return {prefixe for texte in textes for prefixe in prefixes_de(texte or "")}


def porte_un_id(chemin: str, prefixes: set) -> bool:
    """`test_amet9_x.py` porte un id si `amet` est un prefixe de tache connu — `test_sha256_x.py` jamais."""
    return any((py or js).lower() in prefixes for py, js in NOM_AVEC_ID.findall(chemin))


def cite(ligne: str, chemin: str) -> bool:
    """La ligne cite-t-elle `chemin` (en entier ou relatif a django_core), entre backticks, nu ou
    `chemin::symbole` ? Recherche directe : un backtick impair ailleurs sur la ligne n'y change rien."""
    return any(re.search(r"`" + re.escape(nom) + r"(?:`|::)", ligne) for nom in alias(chemin))


def dossier_admis(ligne: str, chemin: str) -> bool:
    """« Nouveau dossier car : » sur la ligne + un chemin cité DANS le dossier de `chemin` : la
    tâche a créé une famille (un fichier par groupe), ses fichiers neufs y sont admis."""
    if not NOUVEAU_DOSSIER.search(ligne):
        return False
    dossier = chemin.rsplit("/", 1)[0]
    return any(c.rsplit("/", 1)[0] == dossier for c in CHEMIN_CITE.findall(ligne))


def fichiers_tests_neufs(ctx) -> list:
    """Chemins de tests que la PR cree (ajout, copie, ou renommage qui change le NOM)."""
    neufs = []
    for c in ctx.changements:
        if not (c.apres and est_fichier_test(c.apres)):
            continue
        renomme_sur_place = c.statut[:1] == "R" and c.avant.rsplit("/", 1)[-1] == c.apres.rsplit("/", 1)[-1]
        if c.statut[:1] in "AC" or (c.statut[:1] == "R" and not renomme_sur_place):
            neufs.append(c.apres)
    return sorted(set(neufs))


def juger(ctx, ids_v2: set) -> tuple:
    """(erreurs, avertissements) — une phrase par fichier de test neuf."""
    erreurs, avertissements = [], []
    neufs = fichiers_tests_neufs(ctx)
    prefixes = prefixes_connus(ctx) if neufs else set()
    for chemin in neufs:
        citantes = [(ident, ligne) for ident, ligne in ctx.taches if cite(ligne, chemin)]
        gelees = [ident for ident, _ in citantes if ident in ids_v2]
        if gelees:
            avertissements.append(f"{chemin} : chemin dicté par la tâche v2 gelée {', '.join(gelees)} "
                                  "(à consolider dans un module existant)")
        elif porte_un_id(chemin, prefixes):
            erreurs.append(f"{chemin} : le nom porte un id de tâche — ajouter le test au module existant "
                           "du module touché (convention : un test par module, pas par tâche)")
        elif (not any(NOUVEAU_FICHIER.search(ligne) for _, ligne in citantes)
              and not any(dossier_admis(ligne, chemin) for _, ligne in ctx.taches)):
            erreurs.append(f"{chemin} : fichier de test neuf sans « Nouveau fichier car : » — ajouter le test à un "
                           "module existant, ou citer ce chemin sur une tâche cochée avec « Nouveau fichier car : »")
    return erreurs, avertissements


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        getattr(flux, "reconfigure", lambda **_: None)(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Garde de placement des tests sur le diff (AMET84).")
    parser.add_argument("--base", default="origin/main", help="référence de base (merge-base avec --tete)")
    parser.add_argument("--tete", default="HEAD", help="commit jugé (défaut HEAD)")
    parser.add_argument("--racine", default=str(ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        mb, tete = cfc.resoudre_base(args.racine, args.base, args.tete)
        ctx = Contexte(args.racine, mb, tete)
    except Echec as exc:
        print(f"check_test_placement : ÉCHEC — {exc}")
        return 1
    ids_v2 = charger_ids_v2(Path(args.racine) / "scripts" / "taches_audit_v2.txt")
    erreurs, avertissements = juger(ctx, ids_v2)
    print(f"check_test_placement : {args.base} (merge-base {mb[:9]}) → {tete[:9]} : "
          f"{len(fichiers_tests_neufs(ctx))} fichier(s) de test neuf(s), tâche(s) cochée(s) : "
          f"{', '.join(i for i, _ in ctx.taches) or 'aucune'}")
    for texte in avertissements:
        print(f"  AVERTISSEMENT {texte}")
    if erreurs:
        print(f"check_test_placement : ÉCHEC — {len(erreurs)} fichier(s) de test mal placé(s)")
        for texte in erreurs:
            print(f"  - {texte}")
        return 1
    print("check_test_placement : OK — placement des tests conforme (AMET84).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
