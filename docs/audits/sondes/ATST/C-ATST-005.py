# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture + ast, ni base ni Django — rejouable à la main)
"""PF7 / ATST : `_cellule_prix_remise` (generate_devis_premium.py, rappelée par legacy_onepage.py) imprime prix catalogue BARRÉ +
prix remisé dans la cellule P.U./total du PDF résidentiel premium et une-page. Son seul test de rendu est
`test_remise_par_ligne.py::TestRenduPdfRemiseParLigne` (`@tag('pdf')`, exclu des shards de fusion par `--exclude-tag=pdf`) ;
AMOT45 ne couvre que l'agricole et le commercial. Détecteur : `repro` vrai tant que le test tagué pdf est là, qu'aucun test NON
tagué pdf/slow n'asserte la cellule (hors AMOT45) ET que ci.yml exclut le tag pdf."""
SONDE = {"constat": "C-ATST-005", "sha": "ae5a7ae4c",
         "attendu": "seul TestRenduPdfRemiseParLigne (pdf) asserte line-through/_cellule_prix_remise pour le résidentiel ; ci.yml : --exclude-tag=pdf -> repro True ; un test non tagué ajouté -> False"}
import ast, re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir():
    RACINE = Path.cwd()
BASE = RACINE / "backend/django_core"
MOTEUR = BASE / "apps/ventes/quote_engine/generate_devis_premium.py"
FAIBLE = BASE / "apps/ventes/tests/test_remise_par_ligne.py"
ONEPAGE = BASE / "apps/ventes/quote_engine/legacy_onepage.py"
APPEL = re.compile(r"_cellule_prix_remise\(")
TOUCHE = re.compile(r"line-through|_cellule_prix_remise")
PREMIUM = re.compile(r"generate_devis_premium|legacy_onepage|generate_premium|rendre_pdf|residential")


def etiquettes(n):
    out = set()
    for d in getattr(n, "decorator_list", ()):
        if isinstance(d, ast.Call) and getattr(d.func, "id", getattr(d.func, "attr", "")) == "tag":
            out |= {a.value for a in d.args if isinstance(a, ast.Constant)}
    return out


def unites(src):
    """(nom, étiquettes, texte) de chaque fonction de module et de chaque méthode (étiquettes de classe héritées)."""
    out = []
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef):
            out.append((n.name, etiquettes(n), ast.get_source_segment(src, n) or ""))
        elif isinstance(n, ast.ClassDef):
            corps = [ast.get_source_segment(src, m) or "" for m in n.body if not isinstance(m, ast.FunctionDef)]
            out.append((n.name + ".<corps>", etiquettes(n), chr(10).join(corps)))
            for m in n.body:
                if isinstance(m, ast.FunctionDef):
                    out.append((n.name + "." + m.name, etiquettes(n) | etiquettes(m), ast.get_source_segment(src, m) or ""))
    return out


def sonde(ctx=None):
    if not FAIBLE.is_file():
        return {"repro": False, "raison": "fichier de test absent : " + FAIBLE.relative_to(RACINE).as_posix()}
    appels = [f.name for f in (MOTEUR, ONEPAGE) if f.is_file() and APPEL.search(f.read_text(encoding="utf-8"))]
    if len(appels) < 2:
        return {"repro": False, "raison": "_cellule_prix_remise n'est plus appelée par premium ET une-page : " + str(appels)}
    ci = (RACINE / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    exclut_pdf = bool(re.search(r"manage\.py test .*--exclude-tag=pdf", ci))
    faible, forts, amot45 = [], [], []
    for p in sorted(BASE.rglob("*.py")):
        s = p.as_posix()
        if "/migrations/" in s or not (p.name.startswith("test") or "/tests/" in s):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if not TOUCHE.search(t):
            continue
        rel = p.relative_to(RACINE).as_posix()
        for nom, tags, seg in unites(t):
            if not TOUCHE.search(seg):
                continue
            if p == FAIBLE and nom.startswith("TestRenduPdfRemiseParLigne") and "pdf" in tags:
                faible.append(nom)
            elif "amot45" in p.name:
                amot45.append(rel + "::" + nom)  # agricole + commercial : ne compte pas
            elif not tags & {"pdf", "slow"} and (APPEL.search(seg) or PREMIUM.search(seg)):
                forts.append(rel + "::" + nom)
    return {"repro": bool(faible) and not forts and exclut_pdf, "ci_exclut_tag_pdf": exclut_pdf,
            "unites_tagguees_pdf_dans_test_remise_par_ligne": faible, "tests_non_tagues_qui_assertent_la_cellule": len(forts),
            "forts": forts, "amot45_ignores": len(amot45)}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
