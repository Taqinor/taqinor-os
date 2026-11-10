"""Dernier passage réussi de la QA nocturne (ADCG16).

Lit le journal hors dépôt écrit par scripts/nightly-qa-lanceur.ps1 (lignes
« AAAA-MM-JJ HH:MM:SS  fin code 0 ») et sort en 1 au-delà de 36 h, ou quand aucun
passage n'est consigné. Stdlib seule. Usage :
    python scripts/nightly_qa_dernier_passage.py [--journal CHEMIN]
"""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

SEUIL_HEURES = 36
LIGNE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+(.*)$")


def journal_par_defaut():
    return Path(os.environ.get("LOCALAPPDATA", "")) / "taqinor" / "nightly-qa.log"


def main(argv=None, maintenant=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, default=None)
    args = parser.parse_args(argv)
    chemin = args.journal or journal_par_defaut()
    maintenant = maintenant or datetime.now()
    lignes = []
    if chemin.is_file():
        for brute in chemin.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = LIGNE.match(brute.strip())
            if m:
                lignes.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), m.group(2)))
    reussis = [quand for quand, texte in lignes if texte.strip() == "fin code 0"]
    if not reussis:
        print(f"aucun passage consigné dans {chemin}")
        return 1
    dernier = reussis[-1]
    heures = (maintenant - dernier).total_seconds() / 3600
    quand, texte = lignes[-1]
    print(f"dernier passage réussi : {dernier:%Y-%m-%d %H:%M} (il y a {heures:.0f} h) ; "
          f"dernière tentative : {quand:%Y-%m-%d %H:%M} {texte}")
    return 1 if heures > SEUIL_HEURES else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
