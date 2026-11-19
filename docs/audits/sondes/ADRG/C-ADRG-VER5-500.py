# flake8: noqa  (sonde HÔTE du vérifie ADRG du 19/11/2026 — sans Django, sans base, sans Docker)
"""C-ADRG-VER5-500 — les genres figés `sales` et `service` d'un SavedReport partent à un rôle livré qui n'a AUCUN code
du module dont ils comptent les lignes.

ADRG158 (D-ADRG-15) a posé `JEU_DU_GENRE = {'stock': 'stock_produits'}` : seul le genre `stock` lit un droit. Le genre
`sales` (`render_sales` : leads de la société par étape, ORM direct, sans portée) et le genre `service`
(`render_service` : tickets SAV par statut) ne lisent ni la lecture ni l'export du module, ni à la programmation
(`SavedReportSerializer.validate`) ni au rendu (`_rendre_legacy`). Rôles livrés qui programment (code d'écriture du
module reporting = `reporting_export`) : Technicien responsable n'a aucun code `crm` ; Admin Ventes n'a aucun code
`sav`. Les jumeaux JSON `reports.py::sales_report` / `service_report` exigent `lecture_source(...)`.

Exécute les VRAIES fonctions (extraites par ast, imports internes remplacés par des talons) : `email_saved_reports`,
`rendre_rapport`, `_proprietaire_inactif`, `_export_du_genre_refuse`, `_rendre_legacy`, `exiger_export_dataset`,
`exiger_lecture_dataset`, `peut_lire_module`, `codes_du_module`, `module_du_chemin`, sur le registre réel des rôles.
Contrôle au passage ADRG156 / ADRG158 (propriétaire désactivé, stock sans `stock_export`) : rien ne doit partir."""
SONDE = {"constat": "C-ADRG-VER5-500", "sha": "aa6ccb840",
         "attendu": "sales/service partent à un propriétaire sans code du module ; inactif et stock-sans-export ne partent pas"}
import ast, datetime, importlib.util, json, pathlib
from types import SimpleNamespace as NS

RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


class _SansImports(ast.NodeTransformer):
    def visit_Import(self, node): return ast.Pass()
    def visit_ImportFrom(self, node): return ast.Pass()


def _charger(rel, noms, g):
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8"))
    for n in arbre.body:
        if isinstance(n, ast.FunctionDef) and n.name in noms:
            n.decorator_list = []
            _SansImports().visit(n)
            mod = ast.fix_missing_locations(ast.Module(body=[n], type_ignores=[]))
            exec(compile(mod, f"{rel}::{n.name}", "exec"), g)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in noms for t in n.targets):
            exec(compile(ast.fix_missing_locations(ast.Module(body=[n], type_ignores=[])), rel, "exec"), g)


def _registre():
    spec = importlib.util.spec_from_file_location("permissions_registre_sonde",
                                                  DJ / "apps/roles/permissions_registre.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DatasetNonAutorise(Exception): pass
class DatasetInconnu(Exception): pass


def sonde(ctx=None):
    reg = _registre()
    roles = {n: list(p) for n, p in reg.CANONICAL_SYSTEM_ROLES}
    journal, envois, whatsapp = [], [], []
    g = {
        "DatasetNonAutorise": DatasetNonAutorise, "DatasetInconnu": DatasetInconnu,
        "_registre_modules": lambda: reg.PERMISSION_MODULE, "MODULE_DES_APPS": {"facturation": "ventes"},
        "get_dataset": lambda nom: {"stock_produits": {"module": None, "chemin": "apps.stock.bi_datasets"}}[nom],
        "logger": NS(warning=lambda *a, **k: None, info=lambda *a, **k: None),
        "_RENDERERS": {"sales": lambda r: (["Étape", "Leads"], [["Nouveau", 7]]),
                       "stock": lambda r: (["Produit"], [["Onduleur"]]),
                       "service": lambda r: (["Statut", "Tickets"], [["Ouvert", 3]])},
        "workbook_bytes": lambda h, r, sheet_title="": b"XLSX",
        "MIME_XLSX": "xlsx",
        "_rendre_dashboard": lambda r: (b"PDF", "t", "t.pdf", "pdf"),
        "_rendre_saved_query": lambda r: (b"XLSX", "t", "t.xlsx", "xlsx"),
        "SavedReport": NS(TargetKind=NS(DASHBOARD="dashboard", QUERY="query")),
        "_casablanca_now": lambda: datetime.datetime(2026, 11, 23, 6, 0),
        "_due_schedules": lambda now: {"daily", "weekly", "monthly"},
        "_rapport_est_du": lambda r, now: True,
        "active_companies": lambda: ["co"],
        "_is_email_configured": lambda: True,
        "journaliser_envoi": lambda r, canal, d, statut, erreur="": journal.append((r.name, canal, statut, erreur)),
        "_send_report_email": lambda r, *a, **k: envois.append(r.name) or True,
        "diffuser_whatsapp": lambda r, base_url="": whatsapp.append(r.name) or (1, "ok"),
    }
    _charger("authentication/permissions.py", {"peut_lire_module", "codes_du_module", "module_du_chemin"}, g)
    _charger("core/data_explorer.py", {"exiger_lecture_dataset", "exiger_export_dataset"}, g)
    _charger("apps/reporting/scheduled_reports.py", {
        "email_saved_reports", "rendre_rapport", "_proprietaire_inactif", "_export_du_genre_refuse",
        "_rendre_legacy", "JEU_DU_GENRE", "MOTIF_SANS_EXPORT_STOCK", "CAUSE_PROPRIETAIRE_INACTIF"}, g)
    g["email_saved_reports"].__globals__["SavedReport"].objects = NS(filter=lambda **k: rapports)

    def user(role, actif=True):
        perms = roles[role]
        return NS(is_active=actif, is_superuser=False, role_id=1, role=NS(permissions=perms),
                  is_admin_role="roles_gerer" in perms, nom=role)

    def rapport(nom, kind, owner, canal="email"):
        return NS(name=nom, pk=nom, target_kind=kind, owner=owner, owner_id=(1 if owner else None), company="co",
                  company_id=1, canal=canal, schedule="weekly", last_sent_at=None, save=lambda **k: None,
                  recipient_list=lambda: ["x@libre.ma"], whatsapp_list=lambda: ["+212600000000"],
                  get_target_kind_display=lambda: kind)

    rapports = [
        rapport("sales_technicien_resp", "sales", user("Technicien responsable")),
        rapport("service_admin_ventes", "service", user("Admin Ventes")),
        rapport("stock_commercial_resp", "stock", user("Commercial responsable")),
        rapport("stock_directeur", "stock", user("Directeur")),
        rapport("dashboard_directeur_inactif", "dashboard", user("Directeur", actif=False)),
        rapport("dashboard_directeur_inactif_wa", "dashboard", user("Directeur", actif=False), canal="whatsapp"),
        rapport("stock_proprietaire_supprime", "stock", None),
    ]
    envoyes = g["email_saved_reports"]()
    lien = {r.name: g["rendre_rapport"](r)[0] is not None for r in rapports}

    module = reg.PERMISSION_MODULE
    codes = lambda role, mod: sorted(c for c in roles[role] if module.get(c) == mod)
    lacunes = {"Technicien responsable": {"programme": "reporting_export" in roles["Technicien responsable"],
                                          "codes_crm": codes("Technicien responsable", "crm")},
               "Admin Ventes": {"programme": "reporting_export" in roles["Admin Ventes"],
                                "codes_sav": codes("Admin Ventes", "sav")}}
    validate = ast.unparse(next(n for n in ast.walk(ast.parse(
        (DJ / "apps/reporting/saved_reports_api.py").read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef) and n.name == "validate"))
    jeu_du_genre = g["JEU_DU_GENRE"]
    partis = set(envois) | set(whatsapp)
    repro = ("sales_technicien_resp" in partis and "service_admin_ventes" in partis
             and lien["sales_technicien_resp"] and lien["service_admin_ventes"]
             and not lacunes["Technicien responsable"]["codes_crm"] and not lacunes["Admin Ventes"]["codes_sav"]
             and set(jeu_du_genre) == {"stock"})
    return {"repro": repro, "observe": {
        "methode": "fonctions réelles exécutées (ast, imports internes en talons) ; registre réel importé",
        "envoyes_par_le_passage": sorted(partis), "nombre_rendu_par_email_saved_reports": envoyes,
        "journal_echec": [j for j in journal if j[2] == "echec"],
        "lien_public_rend_un_fichier": lien,
        "JEU_DU_GENRE": jeu_du_genre,
        "validate_ne_garde_que": [k for k in ("KINDS_AVEC_CIBLE", "JEU_DU_GENRE") if k in validate],
        "roles_livres_sans_code_du_module": lacunes,
        "controle_ADRG156": {"inactif_email_parti": "dashboard_directeur_inactif" in partis,
                             "inactif_whatsapp_parti": "dashboard_directeur_inactif_wa" in partis,
                             "inactif_lien": lien["dashboard_directeur_inactif"]},
        "controle_ADRG158": {"stock_commercial_resp_parti": "stock_commercial_resp" in partis,
                             "stock_commercial_resp_lien": lien["stock_commercial_resp"],
                             "stock_directeur_parti": "stock_directeur" in partis,
                             "stock_proprietaire_supprime_parti": "stock_proprietaire_supprime" in partis}}}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
