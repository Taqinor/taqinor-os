# flake8: noqa  (sonde HÔTE d'audit PF7 « tests qui ne prouvent rien », groupe ATST — sans Django, sans base, sans Docker)
"""C-ATST-006 — `scripts/check_company_fk.py` (garde CI d'isolement : tout modèle métier porte sa société) n'a AUCUN test
qui joue son cas d'échec. Mutant joué sur une copie le 11/11 : `if not ok and key not in exempt:` → `if False:` ; un modèle
`Facture` sans société passe (code de sortie 0) et rien ne rougit. La sonde compte les fichiers de test qui importent ou
lancent la garde ; repro tant qu'il n'y en a aucun."""
SONDE = {"constat": "C-ATST-006", "sha": "ae5a7ae4c",
         "attendu": "aucun fichier de test (scripts/tests, backend) ne charge check_company_fk -> repro True ; un test qui fait rougir la garde sur un modèle sans société -> False"}
import pathlib, re

RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "scripts").is_dir():
    RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
GARDE = RACINE / "scripts" / "check_company_fk.py"
MOTIF = re.compile(r"check_company_fk")
LIGNE_CASSEE = re.compile(r"if\s+not\s+ok\s+and\s+key\s+not\s+in\s+exempt\s*:")


def _fichiers_de_test():
    for base in (RACINE / "scripts" / "tests", RACINE / "backend" / "django_core"):
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            n = p.name
            if n.startswith("test") or "/tests/" in p.as_posix():
                yield p


def sonde(ctx=None):
    if not GARDE.is_file():
        return {"repro": False, "raison": "garde scripts/check_company_fk.py absente"}
    src = GARDE.read_text(encoding="utf-8", errors="replace")
    tests = []
    for p in _fichiers_de_test():
        try:
            if MOTIF.search(p.read_text(encoding="utf-8", errors="replace")):
                tests.append(p.relative_to(RACINE).as_posix())
        except OSError:
            continue
    return {
        "repro": not tests,
        "tests_qui_chargent_la_garde": tests,
        "ligne_de_decision_presente": bool(LIGNE_CASSEE.search(src)),
        "detail": "aucun test ne joue le cas d'échec de la garde d'isolement" if not tests else "un test charge la garde",
    }


if __name__ == "__main__":
    print(sonde())
