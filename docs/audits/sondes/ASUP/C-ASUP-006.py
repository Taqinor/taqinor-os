"""Rejoue crm/fiche_ecritures.py::restaurer_lead (corps réel, ast) sur un lead ABSORBÉ par une fusion (archivé, note « Fusionné dans le lead #1 ») : aucune garde de doublon ni de fusion, le lead redevient vivant et sa prochaine étape est replantée."""
SONDE = {"constat": "C-ASUP-006", "sha": "3acfee471",
         "attendu": "restaurer_lead rend vivant un lead absorbé par une fusion et replante sa prochaine étape, sans refus"}
import ast, contextlib, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
FICHIER = RACINE / "backend/django_core/apps/crm/fiche_ecritures.py"


class Sans(ast.NodeTransformer):  # imports locaux -> noms fournis par l'espace de noms
    def visit_ImportFrom(self, n):
        return [ast.parse(f"{a.asname or a.name} = _{a.asname or a.name}").body[0] for a in n.names]
    visit_Import = lambda s, n: ast.Pass()


def sonde(ctx=None):
    fn = next(n for n in ast.parse(FICHIER.read_text(encoding="utf-8")).body
              if isinstance(n, ast.FunctionDef) and n.name == "restaurer_lead")
    fn = ast.fix_missing_locations(Sans().visit(fn))
    journal = []
    djdb = types.ModuleType("django.db"); djdb.transaction = types.SimpleNamespace(atomic=contextlib.nullcontext)
    sys.modules.setdefault("django", types.ModuleType("django")); sys.modules["django.db"] = djdb
    ns = {"_transaction": djdb.transaction,
          "_activity": types.SimpleNamespace(log_restore=lambda l, u: journal.append("chatter restauré"),
                                             log_bulk_note=lambda l, u, n: journal.append(n)),
          "_assurer_prochaine_etape_apres_succes": lambda l, u: journal.append("prochaine étape replantée")}
    exec(compile(ast.Module([fn], []), "restaurer_lead", "exec"), ns)

    class Lead:
        pk, is_archived, archived_by, archived_at = 2, True, "commercial", "2026-11-01"
        note = "RAS\n[Fusionné dans le lead #1]"
        def save(self, update_fields=None): journal.append(("save", tuple(update_fields or ())))
    lead = Lead()
    refus = None
    try: ns["restaurer_lead"](lead, "commercial_responsable")
    except Exception as e: refus = type(e).__name__
    repro = refus is None and not lead.is_archived and "Fusionné" in lead.note
    return {"repro": repro, "observe": {"refus": refus, "is_archived_apres": lead.is_archived,
                                        "effets": [str(x) for x in journal],
                                        "geste": "Restaurer (LeadWorkspace / liste des archivés, Commercial responsable, Directeur)"}}


if __name__ == "__main__":
    print(sonde())
