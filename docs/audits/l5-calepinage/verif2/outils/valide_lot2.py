"""Validation locale d'un lot de taches v3 (lecture seule) contre les gardes du depot.

Usage : python valide_lot.py <fichier_lot.md>
Verifie, pour chaque ligne `- [ ] ACALnnn — **...** : ...` :
  1. les 14 clauses v3 (check_taches_cablage.clauses_manquantes) ;
  2. la presence de (@model: ...) et d'une categorie ;
  3. les ancres `fichier::symbole` (check_ancres_taches.analyser_tache) ;
  4. le proprietaire de chaque chemin de Files: (doit etre `calepinage`) ;
  5. un `n/a` nu ; la longueur de la ligne.
"""
import re
import sys
from pathlib import Path

ROOT = Path(r"C:/dev/taqinor-os/.claude/worktrees/l5-vague2-integ")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import os
os.chdir(ROOT)

import check_taches_cablage as ctc  # noqa: E402
import check_ancres_taches as cat  # noqa: E402
import check_ownership as co  # noqa: E402

PLAN = "docs/plans/PLAN_AUDIT_CALEPINAGE.md"


def main(chemin):
    reg = co.charger_registre()
    texte = Path(chemin).read_text(encoding="utf-8")
    nb = echecs = 0
    for numero, ligne in enumerate(texte.splitlines(), 1):
        m = ctc._TACHE.match(ligne)
        if not m:
            if ligne.strip().startswith("- ["):
                print(f"L{numero}: ligne de case NON reconnue par le lecteur de taches")
                echecs += 1
            continue
        reste = ctc._CROCHETS_RESIDUELS.sub("", m.group("reste"))
        ident = ctc._IDENTIFIANT.match(reste)
        if not ident:
            print(f"L{numero}: identifiant illisible")
            echecs += 1
            continue
        nb += 1
        t = ctc.Tache(PLAN, numero, m.group("etat"), ident.group("id"), reste)
        pb = []
        manq = ctc.clauses_manquantes(t.normalise, "v3")
        if manq:
            pb.append(f"clauses manquantes : {manq}")
        if not re.search(r"\(@model:\s*(haiku|sonnet|opus)\)", ligne):
            pb.append("(@model: haiku|sonnet|opus) absent")
        if not re.search(r"\((ROUTINE|SCHEMA|ARCH|DECISION|AUTH|COST)\)", ligne):
            pb.append("categorie (ROUTINE|SCHEMA|ARCH|...) absente")
        if re.search(r":\s*n/a\s*(\.|;|$|[A-Z])", ligne):
            pb.append("n/a nu (ecrire `n/a — raison`)")
        res, nb_ancres = cat.analyser_tache(t, False, ROOT)
        for _id, ancre, raison in res:
            pb.append(f"ancre : {ancre} - {raison}")
        chemins = co.chemins_declares(reste)
        if not chemins:
            pb.append("Files: vide ou illisible")
        for c in chemins:
            if "*" in c:
                continue
            p = co.proprietaire(reg, c)
            if reg.est_append_only(c):
                continue  # surface en ajout seul : toute tâche peut la déclarer (comme la vraie garde)
            if p != "calepinage":
                pb.append(f"proprietaire de {c} = {p} (attendu calepinage)")
        try:
            if t.exige_atteignabilite() and not t.fichier_de_montage():
                pb.append("ecran cree sans fichier de montage dans Files: (onglets.js / module.config.jsx / router)")
        except Exception as exc:  # garde : API interne
            pb.append(f"(controle montage non joue : {exc})")
        etat = "OK " if not pb else "KO "
        print(f"{etat}{t.identifiant} ({len(ligne)} car., {nb_ancres} ancres)")
        for p in pb:
            print(f"     - {p}")
        echecs += bool(pb)
    print(f"--- {nb} tache(s), {echecs} en echec")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
