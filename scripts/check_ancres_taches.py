#!/usr/bin/env python3
"""Garde des ancres de taches d'audit (AMET83).

Dans une tache OUVERTE v3 (id hors scripts/taches_audit_v2.txt) :
  1. chaque ancre `chemin.ext::Symbole` doit resoudre sur l'arbre courant
     (AST pour .py via audit_tache.resoudre — aucun second parseur) ;
  2. une ancre de ligne nue `chemin.ext:123` ou `(l.123)` / `l.123` sans
     aucune ancre `::symbole` dans la meme tache est un ECHEC.
Tache v2 : le nombre d'ancres derivees est imprime, jamais bloque.

    python scripts/check_ancres_taches.py        # exit 1 si ECHEC
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_tache as at  # noqa: E402
import check_taches_cablage as ctc  # noqa: E402

_EXT = r"(?:py|jsx?|tsx?|ya?ml|json|md|ps1|sh)"
ANCRE = re.compile(r"`([\w./-]+\.%s)::([A-Za-z_][\w.]*)`" % _EXT)
LIGNE_NUE = re.compile(r"`[\w./-]+\.%s:\d+(?:[-–]\d+)?`|(?<!`)\(l\.\s?\d+[^)]*\)|(?<![\w`(])l\.\s?\d+\b" % _EXT)


def fichier_de(rel: str, racine: Path) -> str:
    """Chemin depot de l'ancre : tel quel, sinon par suffixe unique (`crm/views.py`)."""
    if (racine / rel).is_file():
        return rel
    try:
        suivis = at.git("ls-files", racine=racine).splitlines()
    except Exception:  # noqa: BLE001 — hors depot git : l'ancre reste telle quelle
        return rel
    trouves = [f for f in suivis if f == rel or f.endswith("/" + rel)]
    return trouves[0] if len(trouves) == 1 else rel


def verifier_ancre(rel: str, symbole: str, racine) -> str:
    """'' si l'ancre resout, sinon la raison (francais)."""
    racine = Path(racine)
    rel = fichier_de(rel, racine)
    if rel.endswith(".py"):
        try:
            at.resoudre(f"{rel}::{symbole}", racine)
        except SystemExit as exc:
            return str(exc)
        return ""
    path = racine / rel
    if not path.is_file():
        return f"fichier introuvable : {rel}"
    if symbole.split(".")[-1] not in path.read_text(encoding="utf-8", errors="replace"):
        return f"{rel} : symbole « {symbole} » introuvable"
    return ""


def analyser_tache(tache, v2: bool, racine) -> tuple:
    """(echecs [(id, ancre, raison)], nb_ancres)."""
    ancres = ANCRE.findall(tache.texte)
    if v2:
        return [], len(ancres)
    echecs = []
    for rel, symbole in ancres:
        raison = verifier_ancre(rel, symbole, racine)
        if raison:
            echecs.append((tache.identifiant, f"{rel}::{symbole}", raison))
    if not ancres:  # une ligne ne vaut qu'en complement d'un symbole de la meme tache
        for nue in LIGNE_NUE.findall(tache.texte):
            echecs.append((tache.identifiant, nue, "ancre de ligne nue : citer `fichier::symbole`"))
    return echecs, len(ancres)


def main(argv=None) -> int:
    racine = ctc.ROOT
    ids_v2 = ctc.charger_ids_v2()
    echecs = []
    nb_v3 = anc_v3 = nb_v2 = anc_v2 = 0
    fichiers = [f for f in ctc.fichiers_de_plan() if "PLAN_AUDIT_" in f]
    for tache in ctc.lire_taches(fichiers):
        if tache.etat != " ":
            continue
        v2 = ctc.version_de(tache.identifiant, ids_v2) == "v2"
        res, nb = analyser_tache(tache, v2, racine)
        echecs += res
        if v2:
            nb_v2, anc_v2 = nb_v2 + 1, anc_v2 + nb
        else:
            nb_v3, anc_v3 = nb_v3 + 1, anc_v3 + nb
    for identifiant, ancre, raison in echecs:
        print(f"ECHEC {identifiant} : {ancre} - {raison}".encode("ascii", "replace").decode())
    print(f"Ancres de taches : {nb_v3} tache(s) v3 verifiee(s), {anc_v3} ancre(s) fichier::symbole ; "
          f"{nb_v2} tache(s) v2, {anc_v2} ancre(s) derivee(s) (rapport seul) ; {len(echecs)} echec(s).")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
