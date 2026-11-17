# flake8: noqa  (sonde HÔTE du vérifie ADRG du 17/11/2026 — sans Django, sans base, sans Docker)
"""C-ADRG-VER3-360 — jumeau d'ADRG123 : envoi programmé d'un TABLEAU DE BORD (genre `dashboard`) dont un widget lit
le jeu `stock_produits`, sans `stock_export`.

ADRG123 a fermé le genre `query` (`SavedReportSerializer.validate` et `_rendre_saved_query` appellent
`core/data_explorer.py::exiger_export_dataset`). Le genre `dashboard` rend en PDF, par e-mail à des adresses libres et
par le lien public de 90 jours (`apps/reporting/diffusion_views.py::rapport_partage_public` -> `rendre_rapport`), les
LIGNES de chaque widget (`core/dashboard_data.py::executer_dashboard` -> `data_explorer.run_query`, qui n'exige que la
lecture). Un tableau de bord se crée par `core/views.py::DashboardViewSet` (tout utilisateur interne). La sonde lit ces
corps par ast et calcule, sur le VRAI registre, les rôles livrés qui passent la garde d'écriture reporting, lisent le
stock et n'ont pas `stock_export` (retrait D-ASEC-VER4-1)."""
SONDE = {"constat": "C-ADRG-VER3-360", "sha": "ee9180785",
         "attendu": "validate n'appelle exiger_export_dataset que pour le genre query ; ni _rendre_dashboard ni "
                    "rendre_dashboard_html ni executer_dashboard ne lisent le droit d'export ; DashboardViewSet ouvert "
                    "à tout interne ; rôles touchés = ceux de VER2-200"}
import ast, importlib.util, json, pathlib
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


def _arbre(rel):
    return ast.parse((DJ / rel).read_text(encoding="utf-8"))


def _classe(rel, nom):
    return next(n for n in ast.walk(_arbre(rel)) if isinstance(n, ast.ClassDef) and n.name == nom)


def _fonction(rel, nom, classe=None):
    racine = _classe(rel, classe) if classe else _arbre(rel)
    return next(n for n in ast.walk(racine) if isinstance(n, ast.FunctionDef) and n.name == nom)


def _registre():
    spec = importlib.util.spec_from_file_location("permissions_registre_sonde",
                                                  DJ / "apps/roles/permissions_registre.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _perm_classes(rel, classe):
    for n in _classe(rel, classe).body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "permission_classes" for t in n.targets):
            return [ast.unparse(e) for e in n.value.elts]
    return []


def sonde(ctx=None):
    reg = _registre()
    module_de = dict(reg.PERMISSION_MODULE)
    connus = set(module_de)

    def ecrit(code):
        return (code in connus and not code.endswith(("_voir", "_view"))
                and not code.startswith(("records_scope", "portail_")))

    # 1. validate : l'appel d'export est-il réservé au genre query ?
    validate = _fonction("apps/reporting/saved_reports_api.py", "validate", "SavedReportSerializer")
    appel_sous_query = False
    appel_hors_query = False
    for n in ast.walk(validate):
        if isinstance(n, ast.If) and "TargetKind.QUERY" in ast.unparse(n.test):
            if "exiger_export_dataset" in ast.unparse(n):
                appel_sous_query = True
    nb_appels = ast.unparse(validate).count("exiger_export_dataset(")
    appel_hors_query = nb_appels > (1 if appel_sous_query else 0)

    # 2. Rendu du genre dashboard : aucun appel au droit d'export.
    corps_rendu = "".join(ast.unparse(_fonction("apps/reporting/scheduled_reports.py", f))
                          for f in ("_rendre_dashboard", "rendre_dashboard_html"))
    corps_exec = ast.unparse(_fonction("core/dashboard_data.py", "executer_dashboard"))
    rendu_dashboard_lit_export = "exiger_export_dataset" in corps_rendu or "exiger_export_dataset" in corps_exec
    exec_appelle_run_query = "run_query" in corps_exec
    run_query = ast.unparse(_fonction("core/data_explorer.py", "run_query"))
    run_query_lecture_seule = "exiger_lecture_dataset" in run_query and "exiger_export_dataset" not in run_query

    # 3. Lien public : rendre_rapport aiguille le genre dashboard vers _rendre_dashboard.
    rr = ast.unparse(_fonction("apps/reporting/scheduled_reports.py", "rendre_rapport"))
    aiguille_dashboard = "_rendre_dashboard(report)" in rr
    lien_public = "rendre_rapport" in ast.unparse(_fonction("apps/reporting/diffusion_views.py", "rapport_partage_public"))

    # 4. Création d'un tableau de bord : garde de DashboardViewSet.
    garde_dashboard = _perm_classes("core/views.py", "DashboardViewSet")
    garde_saved = _perm_classes("apps/reporting/saved_reports_api.py", "SavedReportViewSet")
    champs_stock = "'nom'" in (DJ / "apps/stock/bi_datasets.py").read_text(encoding="utf-8") and \
        "'quantite_stock'" in (DJ / "apps/stock/bi_datasets.py").read_text(encoding="utf-8")

    # 5. Rôles livrés (même prédicat que VER2-200).
    touches = []
    for role in reg.CANONICAL_SYSTEM_ROLES:
        nom = role[0]
        codes = set(next(x for x in role if isinstance(x, (list, tuple, set, frozenset))))
        if "roles_gerer" in codes or not any(ecrit(c) for c in codes):
            continue
        ecrit_reporting = any(ecrit(c) and module_de.get(c) == "reporting" for c in codes)
        lit_stock = any(module_de.get(c) == "stock" for c in codes)
        if ecrit_reporting and lit_stock and "stock_export" not in codes:
            touches.append(nom)

    repro = (bool(touches) and appel_sous_query and not appel_hors_query and not rendu_dashboard_lit_export
             and exec_appelle_run_query and run_query_lecture_seule and aiguille_dashboard and lien_public
             and garde_saved == ["IsResponsableOrAdmin"] and champs_stock)
    return {"repro": repro, "observe": {
        "methode": "registre réel importé ; gardes et corps lus par ast",
        "validate_export_seulement_sous_query": appel_sous_query and not appel_hors_query,
        "rendu_dashboard_lit_le_droit_export": rendu_dashboard_lit_export,
        "executer_dashboard_appelle_run_query": exec_appelle_run_query,
        "run_query_exige_lecture_seule": run_query_lecture_seule,
        "lien_public_rend_le_dashboard": aiguille_dashboard and lien_public,
        "garde_dashboard_viewset": garde_dashboard,
        "garde_saved_reports": garde_saved,
        "jeu_stock_produits_nom_et_quantite": champs_stock,
        "roles_livres_touches": touches}}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
