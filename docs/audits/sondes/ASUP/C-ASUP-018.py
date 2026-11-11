"""Lecture ast du chemin de suppression douce d'un lead (LeadViewSet.destroy, soft_delete, récepteurs post_save du Lead) : atteint-il l'annulation des rendez-vous que l'archivage fait (annuler_rendez_vous*) ?"""
SONDE = {"constat": "C-ASUP-018", "sha": "3acfee471",
         "attendu": "le chemin de suppression n'atteint aucune fonction annuler_rendez_vous*, alors que archiver_lead l'appelle"}
import ast, pathlib, sys
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
CIBLE = "annuler_rendez_vous"


def _arbre(rel): return ast.parse((DJ / rel).read_text(encoding="utf-8"))


def _methode(rel, cls, nom):
    c = next(n for n in _arbre(rel).body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(m for m in c.body if isinstance(m, ast.FunctionDef) and m.name == nom)


def _appels(n):
    return {(c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "?")) for c in ast.walk(n) if isinstance(c, ast.Call)}


def _recepteurs_lead():  # fonctions décorées @receiver(..., sender=Lead) de crm
    out = []
    for rel in ("apps/crm/receivers.py", "apps/crm/receivers_cadence.py"):
        for n in _arbre(rel).body:
            if isinstance(n, ast.FunctionDef) and any(isinstance(k.value, ast.Name) and k.value.id == "Lead"
                                                      for d in n.decorator_list if isinstance(d, ast.Call) for k in d.keywords if k.arg == "sender"):
                out.append(n)
    cad = [n for n in _arbre("apps/crm/receivers_cadence.py").body if isinstance(n, ast.FunctionDef) and n.name == "_arreter_cadence_on_archive"]
    return out + cad


def _index_crm():
    idx = {}
    for f in sorted((DJ / "apps/crm").glob("*.py")):
        try: arbre = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError: continue
        for n in arbre.body:
            if isinstance(n, ast.FunctionDef): idx.setdefault(n.name, n)
    return idx


def atteignables(departs, profondeur=3):
    idx, vus, front = _index_crm(), set(), list(departs)
    for _ in range(profondeur + 1):
        suivants = []
        for n in front:
            for nom in _appels(n):
                if nom not in vus:
                    vus.add(nom)
                    if nom in idx and not nom.startswith("_log"): suivants.append(idx[nom])
        front = suivants
    return vus


def sonde(ctx=None):
    departs = [_methode("apps/crm/views.py", "LeadViewSet", "destroy"), _methode("core/models.py", "SoftDeleteModel", "soft_delete")] + _recepteurs_lead()
    suppr = {n for n in atteignables(departs) if n.startswith(CIBLE)}
    arch = {n for n in _appels(next(n for n in _arbre("apps/crm/fiche_bulk.py").body if isinstance(n, ast.FunctionDef) and n.name == "archiver_lead")) if n.startswith(CIBLE)}
    return {"repro": not suppr and bool(arch), "observe": {
        "depart_suppression": ["LeadViewSet.destroy", "SoftDeleteModel.soft_delete"] + [d.name for d in departs[2:]],
        "annulation_rdv_atteinte_par_la_suppression": sorted(suppr) or "AUCUNE",
        "annulation_rdv_appelee_par_archiver_lead": sorted(arch) or "AUCUNE", "methode": "ast"}}


if __name__ == "__main__":
    print(sonde())
