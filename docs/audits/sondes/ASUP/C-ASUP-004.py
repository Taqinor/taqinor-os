"""Lecture ast de monitoring/views.py::ProductionWarrantyViewSet : ModelViewSet sans destroy surchargé ni http_method_names, garde d'écriture IsResponsableOrAdmin sur le module sav — la garantie de production d'un client (base de la compensation due) se supprime en dur, sans garde ni trace métier ; l'écran WarrantiesPage offre le bouton."""
SONDE = {"constat": "C-ASUP-004", "sha": "3acfee471",
         "attendu": "ProductionWarrantyViewSet hérite du destroy de DRF (aucune surcharge, DELETE non exclu) et l'écran appelle la suppression"}
import ast, pathlib, re, sys
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()


def sonde(ctx=None):
    arbre = ast.parse((RACINE / "backend/django_core/apps/monitoring/views.py").read_text(encoding="utf-8"))
    cl = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "ProductionWarrantyViewSet")
    bases = [ast.unparse(b) for b in cl.bases]
    noms = {getattr(s, "name", None) for s in cl.body} | {
        t.id for s in cl.body if isinstance(s, ast.Assign) for t in s.targets if isinstance(t, ast.Name)}
    surcharge = noms & {"destroy", "perform_destroy", "http_method_names"}
    ecran = RACINE / "frontend/src/pages/monitoring/WarrantiesPage.jsx"
    texte = ecran.read_text(encoding="utf-8") if ecran.exists() else ""
    bouton = bool(re.search(r"delete|supprim", texte, re.I))
    repro = any(b.endswith("ModelViewSet") for b in bases) and not surcharge and bouton
    return {"repro": repro, "observe": {"methode": "ast + lecture écran", "bases": bases,
                                        "surcharges_de_suppression": sorted(surcharge),
                                        "ecran_offre_la_suppression": bouton}}


if __name__ == "__main__":
    print(sonde())
