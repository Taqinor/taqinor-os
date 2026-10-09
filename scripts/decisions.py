#!/usr/bin/env python3
"""`decisions.py appliquer` : reecrit les taches « Si (a) : ... ; si (b) : ... »
dont la decision est repondue en leur seule branche repondue (AMET94).

    python scripts/decisions.py appliquer --dry-run     # liste avant / apres
    python scripts/decisions.py appliquer --appliquer   # ecrit les lignes

Sans `--appliquer`, rien n'est ecrit. La ligne et l'id restent (une ligne = une
ligne) ; seule la clause conditionnelle de l'en-tete en gras devient sa branche
repondue, suivie du tag `(@decision: D=a)`. Une etiquette `[GATED: ...]` sur une
decision repondue devient `[D = (a), tranchee le <date>]`.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_decisions as cd  # noqa: E402

ENTETE = re.compile(
    r"^(?P<tete>- \[[^\]]*\]\s*[A-Z][A-Za-z0-9]*\s*—\s*)\*\*(?P<corps>.*?)\*\*(?P<suite> :.*)$")
COUPE = re.compile(r";\s*[Ss]i \(")
ETIQ_GATED = re.compile(r"^\[GATED:[^\]]*\]\s*")


def reecrire(ligne: str, decision: dict):
    """(nouvelle_ligne, None), ou (None, raison) si la branche repondue est absente."""
    m = ENTETE.match(ligne)
    if not m:
        return None, "en-tete en gras introuvable"
    corps = m.group("corps")
    marques = list(cd.CONDITIONNEL.finditer(corps))
    cle = decision["reponse"]
    choisie = None
    for i, mq in enumerate(marques):
        if mq.group(1).lower() == cle:
            fin = marques[i + 1].start() if i + 1 < len(marques) else len(corps)
            choisie = COUPE.split(corps[mq.end():fin], 1)[0].strip().rstrip(";").strip()
            break
    if choisie is None:
        return None, f"branche ({cle}) absente de l'en-tete"
    pre = corps[:marques[0].start()]
    if ETIQ_GATED.match(pre):
        pre = ETIQ_GATED.sub(f"[{decision['id']} = ({cle}), tranchee le {decision['date']}] ", pre)
    nouveau = f"{pre}{choisie} (@decision: {decision['id']}={cle})"
    return f"{m.group('tete')}**{nouveau}**{m.group('suite')}", None


def planifier(racine: Path = ROOT) -> tuple:
    """([(tache, avant, apres)], [(tache, raison)]) des taches ouvertes conditionnelles."""
    decisions = cd.charger_decisions(racine)
    reecritures, impossibles = [], []
    for t in cd.lire_taches_audit(racine):
        if not cd.est_ouverte(t) or not cd.CONDITIONNEL.search(cd.nettoyer(t.texte)):
            continue
        repondues = [d for d in cd.decisions_de_tache(t, decisions) if cd.est_repondue(d)]
        if not repondues:
            continue
        ligne = (racine / t.fichier).read_bytes().decode("utf-8").splitlines()[t.ligne - 1]
        apres, raison = reecrire(ligne, repondues[0])
        if apres is None:
            impossibles.append((t, raison))
        else:
            reecritures.append((t, ligne, apres))
    return reecritures, impossibles


def entete(ligne: str) -> str:
    m = ENTETE.match(ligne)
    return m.group("corps") if m else ligne[:200]


def appliquer(racine: Path = ROOT, ecrire: bool = False) -> int:
    reecritures, impossibles = planifier(racine)
    for t, avant, apres in reecritures:
        print(f"{t.identifiant}  {t.fichier}:{t.ligne}\n"
              f"  avant : {entete(avant)}\n  apres : {entete(apres)}\n")
    for t, raison in impossibles:
        print(f"IMPOSSIBLE {t.identifiant} ({t.fichier}:{t.ligne}) : {raison}")
    if ecrire:
        par_fichier = {}
        for t, _, apres in reecritures:
            par_fichier.setdefault(t.fichier, []).append((t.ligne, apres))
        for rel, modifs in par_fichier.items():
            chemin = racine / rel
            lignes = chemin.read_bytes().decode("utf-8").splitlines(keepends=True)
            for numero, apres in modifs:
                ancienne = lignes[numero - 1]
                lignes[numero - 1] = apres + ancienne[len(ancienne.rstrip("\r\n")):]
            chemin.write_bytes("".join(lignes).encode("utf-8"))
    verbe = "ecrites" if ecrire else "a ecrire (dry-run)"
    print(f"{len(reecritures)} reecriture(s) {verbe}, {len(impossibles)} impossible(s).")
    return 1 if impossibles else 0


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("commande", nargs="?", choices=["appliquer"], default="appliquer")
    parseur.add_argument("--dry-run", action="store_true", help="liste sans ecrire (defaut)")
    parseur.add_argument("--appliquer", action="store_true", help="ecrit les reecritures")
    args = parseur.parse_args(argv)
    return appliquer(ROOT, ecrire=args.appliquer and not args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
