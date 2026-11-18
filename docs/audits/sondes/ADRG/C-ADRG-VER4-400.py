# flake8: noqa  (sonde HÔTE du vérifie ADRG du 18/11/2026 — sans Django, sans base, sans Docker)
"""C-ADRG-VER4-400 — un envoi programmé (SavedReport) continue de partir, par e-mail et par lien public, après la
désactivation de son propriétaire.

ADRG146/147 revérifient au rendu le droit d'EXPORT du propriétaire (`exiger_export_dataset(..., report.owner)`), mais
cette garde ne lit que les codes du rôle : ni elle, ni `exiger_lecture_dataset` / `peut_lire_module`, ni
`email_saved_reports`, ni `rendre_rapport`, ni `resolve_report_token` ne lisent `owner.is_active`. Un propriétaire de
palier administrateur (`roles_gerer` : Directeur, Administrateur) passe même la garde d'export sans condition, et les
trois genres figés (`sales`/`stock`/`service`) ne lisent aucun droit. Le jumeau `core/scheduled_export.py::
_cause_suspension` (APFS103) suspend l'extrait planifié d'un créateur désactivé, et `suspendre_exports_du_createur`
celui d'un créateur supprimé : la règle existe, elle manque à SavedReport."""
SONDE = {"constat": "C-ADRG-VER4-400", "sha": "bc1eca567",
         "attendu": "aucun site du chemin d'envoi d'un SavedReport ne lit owner.is_active ; le jumeau ScheduledExport le lit"}
import ast, importlib.util, json, pathlib
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


def _arbre(rel):
    return ast.parse((DJ / rel).read_text(encoding="utf-8"))


def _fonction(rel, nom):
    return next(n for n in ast.walk(_arbre(rel)) if isinstance(n, ast.FunctionDef) and n.name == nom)


def _src(rel, nom):
    return ast.unparse(_fonction(rel, nom))


def _registre():
    spec = importlib.util.spec_from_file_location("permissions_registre_sonde",
                                                  DJ / "apps/roles/permissions_registre.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sonde(ctx=None):
    chemin = {
        "scheduled_reports.email_saved_reports": _src("apps/reporting/scheduled_reports.py", "email_saved_reports"),
        "scheduled_reports.rendre_rapport": _src("apps/reporting/scheduled_reports.py", "rendre_rapport"),
        "scheduled_reports._rendre_dashboard": _src("apps/reporting/scheduled_reports.py", "_rendre_dashboard"),
        "scheduled_reports.rendre_dashboard_html": _src("apps/reporting/scheduled_reports.py", "rendre_dashboard_html"),
        "scheduled_reports._rendre_saved_query": _src("apps/reporting/scheduled_reports.py", "_rendre_saved_query"),
        "scheduled_reports._rendre_legacy": _src("apps/reporting/scheduled_reports.py", "_rendre_legacy"),
        "diffusion_views.resolve_report_token": _src("apps/reporting/diffusion_views.py", "resolve_report_token"),
        "diffusion_views.rapport_partage_public": _src("apps/reporting/diffusion_views.py", "rapport_partage_public"),
        "data_explorer.exiger_export_dataset": _src("core/data_explorer.py", "exiger_export_dataset"),
        "data_explorer.exiger_lecture_dataset": _src("core/data_explorer.py", "exiger_lecture_dataset"),
        "permissions.peut_lire_module": _src("authentication/permissions.py", "peut_lire_module"),
    }
    lit_is_active = {k: ("is_active" in v) for k, v in chemin.items()}
    export_contourne_par_admin = "is_admin_role" in chemin["data_explorer.exiger_export_dataset"]
    rendu_relit_le_droit_du_proprietaire = (
        "report.owner" in chemin["scheduled_reports._rendre_saved_query"]
        and "report.owner" in chemin["scheduled_reports.rendre_dashboard_html"])
    figes_sans_droit = "owner" not in chemin["scheduled_reports._rendre_legacy"]

    # Témoin : le jumeau extrait planifié (APFS103) suspend un créateur désactivé / supprimé.
    temoin = _src("core/scheduled_export.py", "_cause_suspension")
    temoin_suspend_desactive = "is_active" in temoin
    temoin_suspend_supprime = "pre_delete" in (DJ / "core/apps.py").read_text(encoding="utf-8") and \
        "suspendre_exports_du_createur" in (DJ / "core/apps.py").read_text(encoding="utf-8")
    owner_set_null = "on_delete=models.SET_NULL" in ast.unparse(next(
        n for n in ast.walk(_arbre("apps/reporting/models.py"))
        if isinstance(n, ast.ClassDef) and n.name == "SavedReport"))

    reg = _registre()
    admins = [r[0] for r in reg.CANONICAL_SYSTEM_ROLES
              if "roles_gerer" in set(next(x for x in r if isinstance(x, (list, tuple, set, frozenset))))]

    repro = (not any(lit_is_active.values()) and export_contourne_par_admin and rendu_relit_le_droit_du_proprietaire
             and temoin_suspend_desactive)
    return {"repro": repro, "observe": {
        "methode": "corps lus par ast sur le dépôt ; registre réel importé",
        "chemin_envoi_lit_owner_is_active": lit_is_active,
        "rendu_relit_le_droit_du_proprietaire": rendu_relit_le_droit_du_proprietaire,
        "garde_export_ignoree_pour_palier_admin": export_contourne_par_admin,
        "genres_figes_sans_aucun_droit_du_proprietaire": figes_sans_droit,
        "owner_on_delete_set_null": owner_set_null,
        "temoin_scheduled_export_suspend_createur_desactive": temoin_suspend_desactive,
        "temoin_scheduled_export_suspend_createur_supprime": temoin_suspend_supprime,
        "roles_livres_palier_admin_sans_garde": admins}}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
