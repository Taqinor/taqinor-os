# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture + ast, ni base ni Django — rejouable à la main)
"""PF7 / ATST : `quote_engine/etude_chiffrage.py` pose `masquer_economies |= "economies" in opts.get("sections_masquees", ())`
(lien public « économies » décochée -> PDF résidentiel sans économies). Les seuls tests qui passent `sections_masquees` à
`build_quote_data` / au rendu sont `@tag('pdf')`/`slow`, et `.github/workflows/ci.yml` lance les shards de fusion avec
`--exclude-tag=pdf` : supprimer la ligne ne rougit rien à la fusion. Détecteur : `repro` vrai tant que la ligne existe, que
tous les tests consommateurs sont tagués pdf/slow (au moins un) ET que ci.yml exclut le tag pdf des shards."""
SONDE = {"constat": "C-ATST-004", "sha": "ae5a7ae4c",
         "attendu": "ligne masquer_economies |= ... sections_masquees présente ; tous les tests qui passent sections_masquees à build_quote_data/rendu sont tagués pdf/slow ; ci.yml : --exclude-tag=pdf -> repro True ; un test non tagué ajouté -> False"}
import ast, re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir():
    RACINE = Path.cwd()
BASE = RACINE / "backend/django_core"
MOTEUR = BASE / "apps/ventes/quote_engine/etude_chiffrage.py"
LIGNE = re.compile(r"masquer_economies\s*\|=\s*[\"']economies[\"']\s+in\s+opts\.get\(\s*[\"']sections_masquees[\"']")
CONSOMME = re.compile(r"\b(build_quote_data|rendre_pdf|_texte|generate_premium_devis_pdf|generate_devis_premium)\s*\(")


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
            for m in n.body:
                if isinstance(m, ast.FunctionDef):
                    out.append((n.name + "." + m.name, etiquettes(n) | etiquettes(m), ast.get_source_segment(src, m) or ""))
    return out


def sonde(ctx=None):
    if not MOTEUR.is_file():
        return {"repro": False, "raison": "fichier absent : " + MOTEUR.relative_to(RACINE).as_posix()}
    if not LIGNE.search(MOTEUR.read_text(encoding="utf-8")):
        return {"repro": False, "raison": "la ligne masquer_economies |= ... sections_masquees n'existe plus (ou a changé)"}
    ci = (RACINE / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    exclut_pdf = bool(re.search(r"manage\.py test .*--exclude-tag=pdf", ci))
    taggues, nus = [], []
    for p in sorted(BASE.rglob("*.py")):
        s = p.as_posix()
        if "/migrations/" in s or not (p.name.startswith("test") or "/tests/" in s):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if "sections_masquees" not in t:
            continue
        for nom, tags, seg in unites(t):
            if "sections_masquees" in seg and CONSOMME.search(seg):
                (taggues if tags & {"pdf", "slow"} else nus).append(p.relative_to(RACINE).as_posix() + "::" + nom)
    return {"repro": bool(taggues) and not nus and exclut_pdf, "ci_exclut_tag_pdf": exclut_pdf,
            "tests_consommateurs_tagues_pdf_slow": len(taggues), "tests_consommateurs_non_tagues": len(nus),
            "taggues": taggues, "non_taggues": nus}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
