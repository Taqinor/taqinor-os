"""Rejoue crm/visites_rdv.py::send_due_appointment_reminders sur un crm.Appointment planifié dont le lead est archivé, perdu ou supprimé : le rappel part-il, et l'annulation du lead touche-t-elle ces rendez-vous ?"""
SONDE = {"constat": "C-ASUP-020", "sha": "3acfee471",
         "attendu": "le rappel est envoyé pour un lead archivé/perdu/supprimé ; ni dispatch ni annuler_rendez_vous_du_lead ne lisent l'état du lead ni n'annulent crm.Appointment"}
import ast, datetime, logging, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
NOW = datetime.datetime(2026, 11, 11, 12, 0, tzinfo=datetime.timezone.utc)
ETAT = ("is_archived", "perdu", "is_deleted", "peut_contacter", "ne_plus_contacter")


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


def _val(o, chemin):
    for p in chemin.split("__"): o = getattr(o, p, None)
    return o


def _ok(o, k, v):
    parts = k.split("__"); op = parts.pop() if len(parts) > 1 and parts[-1] in ("in", "gte", "lte") else None
    a = _val(o, "__".join(parts))
    return (a in v if op == "in" else a >= v if op == "gte" else a <= v if op == "lte" else a == v)


class QS:
    def __init__(self, items): self.items = list(items)
    def filter(self, *a, **kw): return QS(o for o in self.items if all(_ok(o, k, v) for k, v in kw.items()))
    def select_related(self, *a): return self
    def __iter__(self): return iter(self.items)


def _fn(rel, nom):
    class SansRelatif(ast.NodeTransformer):
        def visit_ImportFrom(self, n): return ast.Pass() if n.level else n
    n = next(x for x in ast.parse((DJ / rel).read_text(encoding="utf-8")).body if isinstance(x, ast.FunctionDef) and x.name == nom)
    n.decorator_list = []
    return n, ast.unparse(ast.fix_missing_locations(SansRelatif().visit(n)))


def _lit_etat(n):
    return sorted({m.attr for m in ast.walk(n) if isinstance(m, ast.Attribute) and m.attr in ETAT} |
                  {m.id for m in ast.walk(n) if isinstance(m, ast.Name) and m.id in ETAT} |
                  {m.arg.split("__")[-1] for m in ast.walk(n) if isinstance(m, ast.keyword) and m.arg and m.arg.split("__")[-1] in ETAT})


def sonde(ctx=None):
    rel = "apps/crm/visites_rdv.py"
    n_send, src = _fn(rel, "send_due_appointment_reminders")
    n_disp, _ = _fn(rel, "dispatch_appointment_reminder")
    n_ann, _ = _fn("apps/crm/cadence_visite.py", "annuler_rendez_vous_du_lead")
    envoyes = []
    mk = lambda i, **lead: Obj(pk=i, statut="p", reminder_sent=False, scheduled_at=NOW + datetime.timedelta(minutes=30),
                               company_id=1, company=Obj(), lead=Obj(**{"is_archived": False, "perdu": False, "is_deleted": False, **lead}))
    appts = [mk(1, is_archived=True), mk(2, perdu=True), mk(3, is_deleted=True), mk(4)]

    class Appointment:
        Statut = types.SimpleNamespace(PLANIFIE="p", CONFIRME="p")
        objects = QS(appts)
    ns = {"Appointment": Appointment, "datetime": datetime, "APPOINTMENT_REMINDER_MINUTES": 60, "_appt_logger": logging.getLogger("sonde"),
          "tz": types.SimpleNamespace(now=lambda: NOW), "_ramadan_pacing_enabled": lambda c: False,
          "horaires": types.SimpleNamespace(PLAGE_IFTAR_DEBUT=datetime.time(18), PLAGE_IFTAR_FIN=datetime.time(21)),
          "dispatch_appointment_reminder": lambda a: envoyes.append(a.pk) or True}
    exec(src.replace("from django.utils import timezone as tz", "pass"), ns)
    ns["send_due_appointment_reminders"]()
    lit_rappel, lit_disp = _lit_etat(n_send), _lit_etat(n_disp)
    annule_appt = any(isinstance(m, (ast.Name, ast.Attribute)) and getattr(m, "id", getattr(m, "attr", "")) in ("Appointment", "appointments")
                      for m in ast.walk(n_ann))
    dyn = {1, 2, 3} <= set(envoyes)
    return {"repro": dyn and not lit_rappel and not lit_disp and not annule_appt, "observe": {
        "rappels_envoyes_pour(1=archive,2=perdu,3=supprime,4=normal)": envoyes,
        "etat_du_lead_lu_par_send_due": lit_rappel or "AUCUN", "etat_du_lead_lu_par_dispatch": lit_disp or "AUCUN",
        "annuler_rendez_vous_du_lead_touche_crm_Appointment": annule_appt, "methode": "execution + ast"}}


if __name__ == "__main__":
    print(sonde())
