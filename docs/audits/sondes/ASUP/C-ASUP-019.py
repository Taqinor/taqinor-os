"""Lecture ast de « Ma file » (records), du Calendrier/ICS (reporting) et de l'archivage d'un lead : un à-faire manuel ouvert d'un lead archivé ou supprimé est-il exclu à la lecture, ou clos à l'archivage ?"""
SONDE = {"constat": "C-ASUP-019", "sha": "3acfee471",
         "attendu": "ni ma_file / pieces_visibles / _activites_visibles ne lisent l'état archivé ou supprimé de la cible, ni l'archivage ne clôt les à-faire manuels"}
import ast, pathlib, re, sys
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
ETAT = re.compile(r"archiv|is_deleted|perdu|deleted", re.I)
CLORE = re.compile(r"(clo|clor|ferm|termin|done).*activit|activit.*(clo|clor|ferm|termin|done)", re.I)


def _arbre(rel): return ast.parse((DJ / rel).read_text(encoding="utf-8"))


def _fn(rel, qual):
    nodes = _arbre(rel).body
    for p in qual.split("."):
        n = next(x for x in nodes if isinstance(x, (ast.FunctionDef, ast.ClassDef)) and x.name == p); nodes = n.body
    return n


def _mots(n):
    out = set()
    for m in ast.walk(n):
        for v in (getattr(m, "attr", None), getattr(m, "id", None), getattr(m, "arg", None)):
            if isinstance(v, str): out.add(v)
        if isinstance(m, ast.Constant) and isinstance(m.value, str) and len(m.value) < 40: out.add(m.value)
    return out


def _index_crm():
    idx = {}
    for f in sorted((DJ / "apps/crm").glob("*.py")):
        try: arbre = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError: continue
        for n in arbre.body:
            if isinstance(n, ast.FunctionDef): idx.setdefault(n.name, n)
    return idx


def sonde(ctx=None):
    lecteurs = {"records:ma_file": _fn("apps/records/views.py", "ActivityViewSet.ma_file"),
                "records:pieces_visibles": _fn("apps/records/views.py", "pieces_visibles"),
                "records:_scoped": _fn("apps/records/views.py", "_scoped"),
                "reporting:_activites_visibles": _fn("apps/reporting/calendar.py", "_activites_visibles")}
    lus = {k: sorted(m for m in _mots(n) if ETAT.search(m)) for k, n in lecteurs.items()}
    idx = _index_crm()
    departs = [idx["archiver_lead"], idx["_arreter_cadence_on_archive"]]
    appelles, front = set(), departs
    for _ in range(3):
        suivants = []
        for n in front:
            for c in ast.walk(n):
                if isinstance(c, ast.Call):
                    nom = c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "")
                    if nom and nom not in appelles:
                        appelles.add(nom)
                        if nom in idx: suivants.append(idx[nom])
        front = suivants
    clot = sorted(n for n in appelles if CLORE.search(n))
    return {"repro": not any(lus.values()) and not clot, "observe": {
        "etat_de_la_cible_lu_par_les_lecteurs": lus or "AUCUN",
        "l_archivage_clot_des_activites_manuelles": clot or "NON",
        "appelles_par_archivage_extrait": sorted(n for n in appelles if "activ" in n.lower() or "relance" in n.lower()),
        "methode": "ast"}}


if __name__ == "__main__":
    print(sonde())
