"""Rejoue le récepteur crm/receivers.py::_avancer_stage_on_devis_accepted (avec fiche_funnel.avancer_stage_pour_devis) sur le devis accepté d'un lead archivé : le lead passe Signé mais reste archivé, donc hors des « signés »."""
SONDE = {"constat": "C-ASUP-023", "sha": "3acfee471",
         "attendu": "lead archivé + devis accepté : étape = Signé, is_archived reste True, est_lead_signe = False (le lead perdu, lui, est levé)"}
import ast, logging, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


def charger(ns, rel, assignations=()):
    """Exécute dans ns les fonctions de premier niveau (sans décorateur ni import relatif) du fichier, et les assignations nommées."""
    class SansRelatif(ast.NodeTransformer):
        def visit_ImportFrom(self, n): return ast.Pass() if n.level else n
    for n in ast.parse((DJ / rel).read_text(encoding="utf-8")).body:
        ok_assign = isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) in assignations
        if (isinstance(n, ast.FunctionDef) and n.name not in ns) or ok_assign:
            if isinstance(n, ast.FunctionDef): n.decorator_list = []
            try: exec(ast.unparse(ast.fix_missing_locations(SansRelatif().visit(n))), ns)
            except Exception: pass  # défauts d'arguments non résolubles : sans effet sur les fonctions rejouées


def lire_etapes():  # STAGES.py lu par ast : aucune étape écrite ici
    ns = {}; exec(compile(ast.parse((RACINE / "STAGES.py").read_text(encoding="utf-8")), "STAGES.py", "exec"), ns)
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if k.isupper()})


def sonde(ctx=None):
    st = lire_etapes(); envoye = st.STAGES[2]  # étape « devis envoyé » du funnel
    journal = []
    ns = {"logger": logging.getLogger("sonde"), "stages": st, "stage_mod": st, "LeadActivity": types.SimpleNamespace(Kind=types.SimpleNamespace(MODIFICATION="m")),
          "creer_activite": lambda **kw: journal.append(("chatter", kw.get("body"))),
          "activity": types.SimpleNamespace(creer_activite=lambda **kw: journal.append(("chatter", kw.get("body")))),
          "_emit_stage_changed": lambda l, a, b, u: journal.append(("stage", a, b))}
    charger(ns, "apps/crm/fiche_funnel.py", ("_STATUT_VERS_STAGE",))
    charger(ns, "apps/crm/receivers.py")
    charger(ns, "apps/crm/portee_selectors.py")
    obs = {}
    for cas, etat in (("perdu_temoin", {"perdu": True, "is_archived": False}), ("archive", {"perdu": False, "is_archived": True})):
        journal.clear()
        lead = Obj(stage=envoye, company=1, save=lambda update_fields=None: journal.append(("save", update_fields)), **etat)
        devis = Obj(lead=lead, statut="accepte", reference="D-0001")
        try:
            ns["_avancer_stage_on_devis_accepted"](None, devis, None, "envoye")
            err = None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        obs[cas] = {"etape_finale_est_signe": lead.stage == st.CONVERSION_STAGE, "perdu": lead.perdu, "is_archived": lead.is_archived,
                    "est_lead_signe": ns["est_lead_signe"](lead), "erreur": err}
    a = obs["archive"]
    return {"repro": a["erreur"] is None and a["etape_finale_est_signe"] and a["is_archived"] and not a["est_lead_signe"],
            "observe": {**obs, "methode": "execution"}}


if __name__ == "__main__":
    print(sonde())
