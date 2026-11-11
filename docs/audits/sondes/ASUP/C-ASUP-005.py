"""Lecture ast des chemins d'effacement et de rétention (loi 09-08) : quel manager de crm.Lead lisent-ils ? Lead.objects (SoftDeleteManager) exclut les leads en corbeille ; un lead supprimé échappe donc à l'effacement, à la rétention et au nettoyage, et sa donnée personnelle reste en base à vie (la purge à J+30 ne touche que l'entrée de corbeille)."""
SONDE = {"constat": "C-ASUP-005", "sha": "3acfee471",
         "attendu": "les 3 chemins d'effacement / rétention lisent Lead.objects et jamais Lead.all_objects"}
import ast, pathlib, sys
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
CIBLES = [("apps/crm/dsr_provider.py", "_matcher"),
          ("apps/crm/dsr_provider.py", "prospects_hors_duree"),
          ("apps/crm/leads_selectors.py", "lead_ids_par_identifiant")]


def managers(fichier, fonction):
    vus, trouve = set(), False
    for n in ast.walk(ast.parse((DJ / fichier).read_text(encoding="utf-8"))):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fonction:
            trouve = True
            for m in ast.walk(n):
                if isinstance(m, ast.Attribute) and isinstance(m.value, ast.Name) and m.value.id == "Lead" \
                        and m.attr in ("objects", "all_objects"):
                    vus.add(m.attr)
    return trouve, sorted(vus)


def sonde(ctx=None):
    obs, repro = {}, False
    for fichier, fonction in CIBLES:
        trouve, vus = managers(fichier, fonction)
        obs[f"{fichier}::{fonction}"] = vus if trouve else "fonction introuvable"
        if trouve and "objects" in vus and "all_objects" not in vus:
            repro = True
    gestionnaire = (DJ / "core/models.py").read_text(encoding="utf-8")
    obs["SoftDeleteManager_filtre_is_deleted"] = "is_deleted=False" in gestionnaire
    obs["methode"] = "ast"
    return {"repro": repro and obs["SoftDeleteManager_filtre_is_deleted"], "observe": obs}


if __name__ == "__main__":
    print(sonde())
