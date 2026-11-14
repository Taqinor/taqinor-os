# flake8: noqa  (sonde HÔTE du vérifie ADRG du 14/11/2026 — sans Django, sans base, sans Docker)
"""C-ADRG-VER2-200 — envoi programmé d'une requête sauvegardée sur un jeu stock sans `stock_export`.

ADRG76 exige le code d'export du module du jeu (`core/data_explorer.py::exiger_export_dataset`) pour PLANIFIER un
extrait (`core/serializers.py`, `core/scheduled_export.py::_cause_suspension`) et pour exporter un rapport
personnalisé (`apps/reporting/rapport_builder.py`). Le jumeau `SavedReport` (target_kind `query`) envoie la même
requête en XLSX par e-mail à des adresses libres (et par lien de rapport) : création gardée par
`SavedReportViewSet.permission_classes` seul, rendu par `apps/reporting/scheduled_reports.py::_rendre_saved_query`
sans relire le droit. La sonde lit ces gardes par ast, calcule les rôles LIVRÉS sur le VRAI registre
(`apps/roles/permissions_registre.py`) et rend la liste des rôles qui passent la garde d'écriture reporting, lisent
le stock et n'ont pas `stock_export` (retrait voulu par D-ASEC-VER4-1)."""
SONDE = {"constat": "C-ADRG-VER2-200", "sha": "d683286669",
         "attendu": "Commercial responsable et Responsable (reporting_export, stock_voir, sans stock_export) créent un "
                    "envoi programmé d'une requête stock ; ni la création ni le rendu n'appellent exiger_export_dataset ; "
                    "témoin : l'extrait planifié (ADRG76) l'appelle"}
import ast, importlib.util, json, pathlib, sys
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
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


def sonde(ctx=None):
    reg = _registre()
    module_de = dict(reg.PERMISSION_MODULE)
    connus = set(module_de)

    def ecrit(code):  # authentication.models._role_grants_write : ni lecture ni portée ni portail
        return (code in connus and not code.endswith(("_voir", "_view"))
                and not code.startswith(("records_scope", "portail_")))

    # 1. Garde de la vue : permission_classes seule, aucun get_permissions.
    vue = _classe("apps/reporting/saved_reports_api.py", "SavedReportViewSet")
    classes = []
    for n in vue.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "permission_classes" for t in n.targets):
            classes = [ast.unparse(e) for e in n.value.elts]
    a_get_permissions = any(isinstance(n, ast.FunctionDef) and n.name == "get_permissions" for n in vue.body)

    # 2. Création (validate) et rendu : le droit d'export du jeu est-il lu ?
    validate = ast.unparse(_fonction("apps/reporting/saved_reports_api.py", "validate", "SavedReportSerializer"))
    rendu = ast.unparse(_fonction("apps/reporting/scheduled_reports.py", "_rendre_saved_query"))
    lit_creation = "exiger_export_dataset" in validate or "_export'" in validate
    lit_rendu = "exiger_export_dataset" in rendu

    # 3. Témoins ADRG76 : l'extrait planifié lit le droit.
    temoin_serializer = "exiger_export_dataset" in (DJ / "core/serializers.py").read_text(encoding="utf-8")
    temoin_execution = "exiger_export_dataset" in ast.unparse(_fonction("core/scheduled_export.py", "_cause_suspension"))
    jeu_stock = "stock_produits" in (DJ / "apps/stock/bi_datasets.py").read_text(encoding="utf-8")

    # 4. Rôles livrés qui passent IsResponsableOrAdmin en écriture sur le module reporting,
    #    lisent le stock et n'ont pas stock_export (palier administrateur exclu : roles_gerer).
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

    repro = bool(touches) and classes == ["IsResponsableOrAdmin"] and not a_get_permissions \
        and not lit_creation and not lit_rendu and temoin_serializer and temoin_execution and jeu_stock
    return {"repro": repro, "observe": {
        "methode": "registre réel importé ; gardes et corps lus par ast",
        "garde_vue_saved_reports": classes, "get_permissions_present": a_get_permissions,
        "creation_lit_le_droit_export": lit_creation, "rendu_lit_le_droit_export": lit_rendu,
        "temoin_extrait_planifie_lit_le_droit": [temoin_serializer, temoin_execution],
        "jeu_stock_produits_enregistre": jeu_stock,
        "roles_livres_touches": touches}}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
