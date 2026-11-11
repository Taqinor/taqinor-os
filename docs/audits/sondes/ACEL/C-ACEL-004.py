"""Exécute les VRAIES tâches stock/tasks.py::generer_comptages_tournants_task et ::liberer_vagues_planifiees_task avec les VRAIS services services_wms.py sur un faux ORM à 2 sociétés dont la 1re échoue ; liste par ast les autres try/except Exception avalants des tâches installations."""
SONDE = {"constat": "C-ACEL-004", "sha": "3acfee471",
         "attendu": "la 1re société en échec arrête le balayage : la 2e n'est jamais traitée, la tâche rend 0 sans lever ni appeler consigner_echec_tache"}
import ast, datetime, pathlib, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"


class Sans(ast.NodeTransformer):  # imports (même locaux) remplacés par pass : leurs noms viennent de ns
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


def charge(chemin, noms, ns):  # VRAIS corps (décorateurs retirés)
    for n in ast.parse((DJ / chemin).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.FunctionDef) and n.name in noms:
            n.decorator_list = []
            exec(compile(ast.fix_missing_locations(ast.Module([Sans().visit(n)], [])), chemin, "exec"), ns)


class Liste(list):  # faux QuerySet
    def select_related(self, *a): return self
    def filter(self, **kw): return self
    def exclude(self, **kw): return self
    def count(self): return 1


class Atomic:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def commun(trace):
    return {"logger": types.SimpleNamespace(warning=lambda *a, **k: None), "consigner_echec_tache": lambda nom, exc: trace.append(nom),
            "timezone": types.SimpleNamespace(localdate=lambda: datetime.date(2026, 11, 11), now=lambda: datetime.datetime(2026, 11, 11, 12, 0),
                                              localtime=lambda d: d), "datetime": datetime, "transaction": types.SimpleNamespace(atomic=Atomic)}


def rejeu_comptage():
    traites, trace = [], []
    class Plan(types.SimpleNamespace):
        def est_du(self, d): return True
        def save(self, update_fields=None): pass
    plans = Liste([Plan(company_id=i, company=n, classe_abc="A", frequence_jours=30) for i, n in ((1, "A"), (2, "B"))])
    def classes(company, depuis, jusqu_a):
        if company == "A": raise ValueError("donnée corrompue chez la société A")
        return {10: "A"}
    LI = type("LI", (), {"__init__": lambda s, **k: None, "objects": types.SimpleNamespace(bulk_create=lambda l: l)})
    ns = {**commun(trace), "FENETRE_ROTATION_JOURS": 365, "classes_abc_produits": classes,
          "PlanComptageTournant": types.SimpleNamespace(objects=types.SimpleNamespace(filter=lambda **k: plans)),
          "Produit": types.SimpleNamespace(objects=types.SimpleNamespace(filter=lambda **k: [types.SimpleNamespace(quantite_stock=3)])),
          "InventaireSession": types.SimpleNamespace(objects=types.SimpleNamespace(create=lambda **k: types.SimpleNamespace(**k))),
          "LigneInventaire": LI, "create_with_reference": lambda m, p, c, save: traites.append(c) or save("INV-" + c)}
    charge("apps/stock/services_wms.py", {"generer_comptages_tournants"}, ns)
    charge("apps/stock/tasks.py", {"generer_comptages_tournants_task"}, ns)
    return _lance(ns["generer_comptages_tournants_task"], "B", traites, trace)


def rejeu_vagues():
    traites, trace = [], []
    MO = types.SimpleNamespace(MANUEL="manuel", AUTO_HEURE="heure", AUTO_SEUIL="seuil")
    vagues = Liste([types.SimpleNamespace(company_id=i, company=n, reference="V-" + n, mode_liberation="seuil", seuil_lignes=1,
                                          lignes=Liste()) for i, n in ((1, "A"), (2, "B"))])
    def lancer(vague):
        if vague.company == "A": raise RuntimeError("panne chez la société A")
        traites.append(vague.company)
    ns = {**commun(trace), "VaguePicking": types.SimpleNamespace(Statut=types.SimpleNamespace(BROUILLON="brouillon"), ModeLiberation=MO,
                                                                    objects=types.SimpleNamespace(filter=lambda **k: vagues)),
          "AchatsParametres": types.SimpleNamespace(for_company=lambda c: types.SimpleNamespace(heure_coupure_vagues=None)), "lancer_vague": lancer}
    charge("apps/stock/services_wms.py", {"liberer_vagues_planifiees"}, ns)
    charge("apps/stock/tasks.py", {"liberer_vagues_planifiees_task"}, ns)
    return _lance(ns["liberer_vagues_planifiees_task"], "B", traites, trace)


def _lance(tache, seconde, traites, trace):
    try: retour, exc = tache(), None
    except Exception as e: retour, exc = None, f"{type(e).__name__}: {e}"  # noqa: BLE001 — une exception levée = signal task_failure = tracé
    return {"retour": retour, "exception_levee": exc, "seconde_societe_traitee": seconde in traites,
            "appels_consigner_echec_tache": len(trace),
            "defaut": exc is None and seconde not in traites and not trace}


def avalants(chemin, noms):  # try/except Exception sans raise, avec : dans une boucle ? consigne ?
    sortie = []
    for f in ast.parse((DJ / chemin).read_text(encoding="utf-8")).body:
        if not (isinstance(f, ast.FunctionDef) and f.name in noms): continue
        boucles = [b for b in ast.walk(f) if isinstance(b, ast.For)]
        for h in (x for x in ast.walk(f) if isinstance(x, ast.ExceptHandler) and getattr(x.type, "id", "") == "Exception"):
            corps = ast.Module(h.body, [])
            noms_appeles = {getattr(c.func, "id", getattr(c.func, "attr", "")) for c in ast.walk(corps) if isinstance(c, ast.Call)}
            if not any(isinstance(x, ast.Raise) for x in ast.walk(corps)):
                sortie.append({"fonction": f"{chemin}::{f.name}", "ligne": h.lineno, "dans_une_boucle_de_societes": any(h in ast.walk(b) for b in boucles),
                               "consigne_dans_le_journal": "consigner_echec_tache" in noms_appeles})
    return sortie


def sonde(ctx=None):
    try: comptage, vagues = rejeu_comptage(), rejeu_vagues()
    except Exception as e:  # noqa: BLE001 — un correctif qui change les dépendances rend la sonde non concluante
        return {"repro": False, "observe": {"methode": "ast + faux ORM", "inconclusif": f"{type(e).__name__}: {e}"}}
    autres = avalants("apps/stock/tasks.py", {"generer_comptages_tournants_task", "liberer_vagues_planifiees_task"}) + \
        avalants("apps/installations/tasks.py", {"purger_positions_gps_task", "generer_interventions_recurrentes_task"})
    return {"repro": comptage["defaut"] or vagues["defaut"], "observe": {
        "methode": "VRAIES tâches + VRAIS services exécutés sur faux ORM (2 sociétés, la 1re lève) ; autres emplacements lus par ast",
        "scenario": "société A lève, société B saine ; le signal task_failure (seul appelant de consigner_echec_tache) ne part que si la tâche lève",
        "stock.generer_comptages_tournants": comptage, "stock.liberer_vagues_planifiees": vagues,
        "emplacements_try_except_Exception_sans_raise": autres}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
