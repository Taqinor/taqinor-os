"""Lecture ast de crm/clients_views.py::ClientViewSet.anonymize : l'action « Anonymiser (RGPD) » de la fiche client n'efface que la fiche client (anonymiser_client) ; elle n'appelle ni anonymiser_lead pour ses leads, ni l'effacement des ventes (e-mails journalisés), ni le chemin commun core.dsr — les leads du client gardent nom, téléphone, e-mail et GPS."""
SONDE = {"constat": "C-ASUP-008", "sha": "3acfee471",
         "attendu": "anonymize appelle anonymiser_client et aucune fonction d'effacement des leads ni des ventes"}
import ast, pathlib, sys
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
FICHIER = RACINE / "backend/django_core/apps/crm/clients_views.py"
ATTENDUS = ("anonymiser_lead", "erase_crm", "erase_ventes", "effacer", "traiter_demande")


def sonde(ctx=None):
    arbre = ast.parse(FICHIER.read_text(encoding="utf-8"))
    classe = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == "ClientViewSet")
    action = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == "anonymize")
    appels = sorted({(c.func.id if isinstance(c.func, ast.Name) else c.func.attr)
                     for c in ast.walk(action) if isinstance(c, ast.Call)
                     and isinstance(c.func, (ast.Name, ast.Attribute))})
    manquants = [a for a in ATTENDUS if a not in appels]
    repro = "anonymiser_client" in appels and len(manquants) == len(ATTENDUS)
    return {"repro": repro, "observe": {"methode": "ast", "appels_de_anonymize": appels,
                                        "effacements_absents": manquants,
                                        "geste": "Anonymiser (RGPD) sur la fiche client (ClientRgpdActions, Directeur)"}}


if __name__ == "__main__":
    print(sonde())
