"""Rejoue crm/views.py::LeadViewSet.archiver et fiche_bulk.py::archiver_lead sur un lead signé : l'archivage n'est pas refusé et le lead sort des « signés » (est_lead_signe) alors que ses pièces restent actives."""
SONDE = {"constat": "C-ASUP-022", "sha": "3acfee471",
         "attendu": "archiver un lead signé réussit sans garde ; est_lead_signe passe de True à False"}
import ast, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


def extraire(rel, qual):
    class SansRelatif(ast.NodeTransformer):
        def visit_ImportFrom(self, n): return ast.Pass() if n.level else n
    nodes = ast.parse((DJ / rel).read_text(encoding="utf-8")).body
    for p in qual.split("."):
        n = next(x for x in nodes if isinstance(x, (ast.FunctionDef, ast.ClassDef)) and x.name == p); nodes = n.body
    n.decorator_list = []
    return ast.unparse(ast.fix_missing_locations(SansRelatif().visit(n)))


def lire_etapes():  # STAGES.py lu par ast : aucune étape écrite ici
    ns = {}; exec(compile(ast.parse((RACINE / "STAGES.py").read_text(encoding="utf-8")), "STAGES.py", "exec"), ns)
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if k.isupper()})


def sonde(ctx=None):
    st = lire_etapes()
    journal = []
    lead = Obj(pk=1, stage=st.CONVERSION_STAGE, perdu=False, is_archived=False, archived_by=None, archived_at=None,
               save=lambda update_fields=None: journal.append(("save", update_fields)))
    ns = {"stage_mod": st, "timezone": types.SimpleNamespace(now=lambda: 0),
          "activity": types.SimpleNamespace(log_archive=lambda l, u: journal.append("chatter"), log_bulk_note=lambda *a: None),
          "annuler_rendez_vous_sur_arret": lambda l, u, cause: journal.append("rdv_annules"),
          "status": types.SimpleNamespace(HTTP_409_CONFLICT=409), "Response": lambda d=None, status=200: Obj(data=d, status_code=status),
          "LeadSerializer": lambda l, context=None: Obj(data={})}
    dj, db = types.ModuleType("django"), types.ModuleType("django.db")
    class Tx:
        def __enter__(s): return s
        def __exit__(s, *a): return False
    db.transaction = types.SimpleNamespace(atomic=lambda: Tx())
    avant = {n: sys.modules.get(n) for n in ("django", "django.db")}
    sys.modules.update({"django": dj, "django.db": db})
    try:
        exec(extraire("apps/crm/fiche_bulk.py", "archiver_lead"), ns)
        exec(extraire("apps/crm/portee_selectors.py", "est_lead_signe"), ns)
        exec(extraire("apps/crm/views.py", "LeadViewSet.archiver"), ns)
        signe_avant = ns["est_lead_signe"](lead)
        vue = Obj(get_object=lambda: lead)
        try:
            rep = ns["archiver"](vue, Obj(user=Obj(pk=3)), pk=1)
            issue = getattr(rep, "status_code", "execute")
        except Exception as e:  # un refus (409) levé par le geste = comportement corrigé
            issue = f"{type(e).__name__}: {e}"
    finally:
        for n, m in avant.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    signe_apres = ns["est_lead_signe"](lead)
    return {"repro": signe_avant and not signe_apres and lead.is_archived and issue in (200, "execute"), "observe": {
        "est_lead_signe_avant": signe_avant, "est_lead_signe_apres_archivage": signe_apres, "lead_archive": lead.is_archived,
        "issue_du_geste": issue, "journal": journal, "methode": "execution"}}


if __name__ == "__main__":
    print(sonde())
