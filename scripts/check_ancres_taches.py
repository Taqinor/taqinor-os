#!/usr/bin/env python3
"""Garde des ancres de taches d'audit (AMET83).

Dans une tache OUVERTE v3 (id hors scripts/taches_audit_v2.txt) :
  1. chaque ancre `chemin.ext::Symbole` doit resoudre sur l'arbre courant
     (AST pour .py via audit_tache.resoudre — aucun second parseur) ;
  2. une ancre de ligne nue `chemin.ext:123` ou `(l.123)` / `l.123` sans
     aucune ancre `::symbole` dans la meme tache est un ECHEC.
Option --base <ref> (defaut origin/main) : seules les taches v3 TOUCHEES (id absent du plan
au merge-base(<ref>, HEAD), ou ligne modifiee depuis) font echouer ; les autres vont au rapport.
Jamais la POINTE de <ref> : une branche en retard ne « touche » pas ce que seule la base a change
(meme resolution que check_forme_code.resoudre_base). Base indisponible ou clone superficiel :
tout est touche (echec ferme). « Meme clause » = la tache entiere.
Tache v2 : le nombre d ancres derivees est imprime, jamais bloque.

    python scripts/check_ancres_taches.py        # exit 1 si ECHEC
"""
import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_tache as at  # noqa: E402
import check_forme_code as cfc  # noqa: E402
import check_taches_cablage as ctc  # noqa: E402
from forme_code.socle import Echec  # noqa: E402

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


def _methode_existe(path: Path, symbole: str) -> bool:
    """`module::test_x` sans sa classe : vrai si une fonction/méthode porte ce nom (forme courte)."""
    if "." in symbole or not path.is_file():
        return False
    try:
        arbre = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return False
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == symbole
               for n in ast.walk(arbre))


#: La clause « Test rouge d'abord » nomme le test que la tâche CRÉERA (règle (b) : dans le
#: module de test existant) : ses ancres ne sont jamais résolues.
TEST_ROUGE = re.compile(r"Test rouge d.abord\s*:(.*?)(?=Preuve en direct|Hors p[ée]rim[èe]tre|Test-du-test|"
                        r"Source r[ée]elle|Appelants\s*:|\(gen |Files\s*:|$)", re.S)


def _hors_test_rouge(texte: str) -> str:
    return TEST_ROUGE.sub("Test rouge d'abord : (test à créer)", texte)


def verifier_ancre(rel: str, symbole: str, racine) -> str:
    """'' si l'ancre resout, sinon la raison (francais)."""
    racine = Path(racine)
    rel = fichier_de(rel, racine)
    if rel.endswith(".py"):
        try:
            at.resoudre(f"{rel}::{symbole}", racine)
        except SystemExit as exc:
            return "" if _methode_existe(racine / rel, symbole) else str(exc)
        return ""
    path = racine / rel
    if not path.is_file():
        return f"fichier introuvable : {rel}"
    if symbole.split(".")[-1] not in path.read_text(encoding="utf-8", errors="replace"):
        return f"{rel} : symbole « {symbole} » introuvable"
    return ""


def analyser_tache(tache, v2: bool, racine) -> tuple:
    """(echecs [(id, ancre, raison)], nb_ancres)."""
    ancres = ANCRE.findall(_hors_test_rouge(tache.texte))
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


def _git(racine, *args, timeout=60):
    try:
        p = subprocess.run(["git", *args], cwd=racine, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def merge_base(base: str, racine) -> str | None:
    """merge-base(base, HEAD) par check_forme_code.resoudre_base (fetch CI complet de origin/main) ;
    None si la base est introuvable ou le clone superficiel (tout est alors touche)."""
    try:
        return cfc.resoudre_base(racine, base, "HEAD")[0]
    except Echec as exc:
        print(_ascii(f"Avis : {exc}"))
        return None


def lignes_a_la_base(base: str, rel: str, racine) -> dict:
    """{id: ligne} du plan `rel` au `base` ; {} si le fichier est absent a la base."""
    brut = _git(racine, "show", f"{base}:{rel}") or ""
    return {m.group("id"): m.group(0).rstrip() for m in
            re.finditer(r"^- \[.\]\s*(?P<id>[A-Z][A-Za-z0-9]*[0-9]+)\b.*$", brut, re.M)}


def _ascii(texte: str) -> str:
    return texte.encode("ascii", "replace").decode()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Garde des ancres de taches (AMET83)")
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)
    racine = ctc.ROOT
    ids_v2 = ctc.charger_ids_v2()
    mb = merge_base(args.base, racine)
    dispo = mb is not None
    if not dispo:
        print("Avis : base indisponible - toutes les taches v3 traitees comme touchees")
    bloquants, rapport = [], []
    nb_v3 = anc_v3 = nb_v2 = anc_v2 = 0
    for rel in [f for f in ctc.fichiers_de_plan() if "PLAN_AUDIT_" in f]:
        base_lignes = lignes_a_la_base(mb, rel, racine) if dispo else {}
        for tache in ctc.lire_taches([rel]):
            if tache.etat != " ":
                continue
            v2 = ctc.version_de(tache.identifiant, ids_v2) == "v2"
            res, nb = analyser_tache(tache, v2, racine)
            if v2:
                nb_v2, anc_v2 = nb_v2 + 1, anc_v2 + nb
                continue
            nb_v3, anc_v3 = nb_v3 + 1, anc_v3 + nb
            ligne = f"- [{tache.etat}] {tache.texte}".rstrip()
            touchee = not dispo or base_lignes.get(tache.identifiant) != ligne
            (bloquants if touchee else rapport).extend((rel,) + e for e in res)
    for rel, identifiant, ancre, raison in bloquants:
        print(_ascii(f"ECHEC {identifiant} : {ancre} - {raison}"))
    if rapport:
        print("Rapport (taches non touchees, a corriger par leur proprietaire) :")
    for rel, identifiant, ancre, raison in rapport:
        print(_ascii(f"  {rel} {identifiant} : {ancre} - {raison}"))
    print(f"Ancres de taches : {nb_v3} tache(s) v3 verifiee(s), {anc_v3} ancre(s) fichier::symbole ; "
          f"{nb_v2} tache(s) v2, {anc_v2} ancre(s) derivee(s) (rapport seul) ; "
          f"{len(bloquants)} echec(s) bloquant(s), {len(rapport)} en rapport.")
    return 1 if bloquants else 0


if __name__ == "__main__":
    sys.exit(main())
