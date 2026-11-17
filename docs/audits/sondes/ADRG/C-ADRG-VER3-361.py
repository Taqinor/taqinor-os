# flake8: noqa  (sonde HÔTE du vérifie ADRG du 17/11/2026 — sans Django, sans base, sans Docker)
"""C-ADRG-VER3-361 — contournement d'ADRG123 par PATCH : un responsable sans `stock_export` réoriente vers une adresse
libre l'envoi programmé `query` (jeu `stock_produits`) d'un AUTRE propriétaire.

`apps/reporting/saved_reports_api.py::SavedReportViewSet` ne borne pas les rapports à leur propriétaire (TenantMixin
seul, aucun get_queryset / ProprietaireSeulMixin) ; `SavedReportSerializer.validate` n'appelle
`exiger_export_dataset` que si la requête n'est pas partielle ou touche `cible_id`/`target_kind` — un PATCH
`{"recipients": ...}` le saute ; `scheduled_reports.py::_rendre_saved_query` relit le droit au nom de `report.owner`
(le Directeur, qui l'a). Seule borne : la cible doit être visible de l'acteur (`dashboards_visibles_q` : la sienne,
PARTAGÉE, ou sans propriétaire). Rôles calculés sur le VRAI registre (même prédicat que VER2-200)."""
SONDE = {"constat": "C-ADRG-VER3-361", "sha": "ee9180785",
         "attendu": "PATCH recipients d'un rapport query d'autrui : aucun appel au droit d'export de l'acteur ; rendu au "
                    "nom du propriétaire ; queryset non borné au propriétaire"}
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


class _Self:  # stand-in du serializer pour évaluer la condition de garde
    def __init__(self, partial): self.partial = partial


def sonde(ctx=None):
    reg = _registre()
    module_de = dict(reg.PERMISSION_MODULE)
    connus = set(module_de)

    def ecrit(code):
        return (code in connus and not code.endswith(("_voir", "_view"))
                and not code.startswith(("records_scope", "portail_")))

    # 1. Le ViewSet ne borne pas au propriétaire.
    vue = _classe("apps/reporting/saved_reports_api.py", "SavedReportViewSet")
    bases = [ast.unparse(b) for b in vue.bases]
    a_get_queryset = any(isinstance(n, ast.FunctionDef) and n.name == "get_queryset" for n in vue.body)
    borne_proprietaire = a_get_queryset or any("Proprietaire" in b for b in bases)

    # 2. Condition de la garde ADRG123 dans validate, évaluée pour un PATCH {"recipients": ...}.
    validate = _fonction("apps/reporting/saved_reports_api.py", "validate", "SavedReportSerializer")
    garde = next(n for n in ast.walk(validate) if isinstance(n, ast.If)
                 and "exiger_export_dataset" in ast.unparse(n) and "TargetKind.QUERY" in ast.unparse(n.test))
    cond = ast.unparse(garde.test)
    ns = {"kind": "query", "SavedReport": type("SR", (), {"TargetKind": type("TK", (), {"QUERY": "query"})})}
    patch_recipients = eval(cond, dict(ns, self=_Self(True), attrs={"recipients": "x@exemple.ma"}))
    patch_cible = eval(cond, dict(ns, self=_Self(True), attrs={"cible_id": 1}))
    creation = eval(cond, dict(ns, self=_Self(False), attrs={"recipients": "x@exemple.ma"}))
    recipients_ecrivable = "'recipients'" in ast.unparse(_classe("apps/reporting/saved_reports_api.py", "SavedReportSerializer"))

    # 3. Rendu au nom du propriétaire ; visibilité = partagé / sans propriétaire inclus.
    rendu = ast.unparse(_fonction("apps/reporting/scheduled_reports.py", "_rendre_saved_query"))
    rendu_au_proprietaire = "exiger_export_dataset(requete.dataset, report.owner)" in rendu
    vis = ast.unparse(_fonction("core/dashboard_partage.py", "dashboards_visibles_q"))
    visible_si_partage = "partage" in vis and "owner__isnull" in vis

    # 4. Rôles livrés : écriture reporting (passe IsResponsableOrAdmin en PATCH), lisent le stock, sans stock_export.
    touches = []
    for nom, codes in ((r[0], set(next(x for x in r if isinstance(x, (list, tuple, set, frozenset)))))
                       for r in reg.CANONICAL_SYSTEM_ROLES):
        if "roles_gerer" in codes or not any(ecrit(c) for c in codes):
            continue
        if any(ecrit(c) and module_de.get(c) == "reporting" for c in codes) \
                and any(module_de.get(c) == "stock" for c in codes) and "stock_export" not in codes:
            touches.append(nom)

    repro = (bool(touches) and not borne_proprietaire and not patch_recipients and patch_cible and creation
             and recipients_ecrivable and rendu_au_proprietaire and visible_si_partage)
    return {"repro": repro, "observe": {
        "methode": "registre réel importé ; corps lus par ast ; condition de garde évaluée",
        "bases_viewset": bases, "queryset_borne_au_proprietaire": borne_proprietaire,
        "condition_garde": cond,
        "garde_jouee_sur": {"patch_recipients": bool(patch_recipients), "patch_cible_id": bool(patch_cible),
                            "creation": bool(creation)},
        "recipients_ecrivable": recipients_ecrivable,
        "rendu_relit_le_droit_du_proprietaire": rendu_au_proprietaire,
        "cible_visible_si_partagee_ou_sans_proprietaire": visible_si_partage,
        "roles_livres_touches": touches}}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
