"""Rejoue deux maillons : (1) stock/services.py::_log_revision_change écrit le prix d'achat d'un BCF dans records.Comment ; (2) records/views.py::CommentViewSet.list (VRAIES get_permissions et pieces_visibles) ne l'exclut pas pour un rôle livré sans prix_achat_voir."""
SONDE = {"constat": "C-ALEC-003", "sha": "ae5a7ae4c",
         "attendu": "le commentaire de révision porte prix_achat_unitaire ; la liste sans cible exclut leads/modules refusés mais JAMAIS achats : 10 rôles livrés sans prix_achat_voir le lisent"}
import ast, pathlib, runpy, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace


def noeud(chemin, nom, classe=None):  # nœud AST (fonction, classe, affectation) d'un fichier du dépôt
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    corps = arbre.body if not classe else next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body
    return next(n for n in corps if getattr(n, "name", None) == nom or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == nom))


def reel(chemin, nom, classe=None, ns=None):  # CORPS RÉEL compilé (décorateurs et imports locaux retirés : leurs noms viennent de ns)
    n = noeud(chemin, nom, classe); ns = {} if ns is None else ns; n.decorator_list = []
    class Sans(ast.NodeTransformer):  # imports (même imbriqués) remplacés par pass
        visit_Import = visit_ImportFrom = lambda s, b: ast.Pass()
    n = Sans().visit(n)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n], type_ignores=[])), chemin, "exec"), ns)
    return ns[nom]


def constantes(chemin):  # constantes littérales de module (READ_ACTIONS…)
    sortie = {}
    for n in ast.parse((DJ / chemin).read_text(encoding="utf-8")).body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            try: sortie[n.targets[0].id] = ast.literal_eval(n.value)
            except ValueError: pass
    return sortie


def noyau():  # (R, P, comptes) : registre vivant, VRAIES gardes d'authentication/permissions.py, vrais accesseurs de CustomUser, un compte par rôle LIVRÉ interne
    R = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    rp = types.ModuleType("rest_framework.permissions"); rp.SAFE_METHODS, rp.BasePermission = ("GET", "HEAD", "OPTIONS"), type("BasePermission", (), {})
    avant = {n: sys.modules.get(n) for n in ("rest_framework", "rest_framework.permissions")}
    sys.modules.update({"rest_framework": types.ModuleType("rest_framework"), "rest_framework.permissions": rp})
    try:
        P = {"__name__": "authentication.permissions"}; exec(compile((DJ / "authentication/permissions.py").read_text(encoding="utf-8"), "permissions.py", "exec"), P)
    finally:
        for n, m in avant.items(): sys.modules.pop(n, None) if m is None else sys.modules.update({n: m})
    P["enregistrer_registre_modules"](R["PERMISSION_MODULE"], octrois_lecture=R["OCTROIS_LECTURE"])
    cls = ast.parse("class U:\n    pass").body[0]
    cls.body = [n for n in noeud("authentication/models.py", "CustomUser").body if getattr(n, "name", "") in (
        "is_admin_role", "is_responsable", "_role_grants_write", "has_erp_permission", "can_view_buy_prices", "can_view_marge", "can_view_activity_log")]
    U = {}; exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "models.py", "exec"), U); U = U["U"]; U.ROLE_ADMIN, U.ROLE_RESPONSABLE = "admin", "responsable"
    comptes = {}
    for nom, perms in R["CANONICAL_SYSTEM_ROLES"]:
        if not nom.startswith("Portail"):
            c = U(); c.__dict__.update(is_superuser=False, is_authenticated=True, portee="interne", role_legacy="normal", role_id=1, id=len(comptes) + 1, role=NS(nom=nom, permissions=list(perms)))
            comptes[nom] = c
    return R, P, comptes


def vue(chemin): return type("Vue", (), {"__module__": chemin[:-3].replace("/", ".")})()  # vue factice : seul le MODULE Python réel compte (module_de_la_vue)


def gardes(P, chemin, classe, action):  # exécute la VRAIE get_permissions de la classe pour ``action``
    return reel(chemin, "get_permissions", classe, {**P, **constantes(chemin)})(NS(action=action))


def passent(comptes, liste, v, methode="GET"):  # rôles LIVRÉS qui franchissent TOUTES les gardes (vraies classes) sur la vue v
    return sorted(n for n, c in comptes.items() if all(g.has_permission(NS(user=c, method=methode), v) for g in liste))


class Q:  # Q de Django, réduit aux feuilles (clé, valeur) : suffit pour savoir ce que la liste exclut
    def __init__(s, **kw): s.f = list(kw.items())
    def __and__(s, o): r = Q(); r.f = s.f + o.f; return r
    __or__ = __and__
    def __invert__(s): return s


class QS:
    def __init__(s): s.exclu = None
    def exclude(s, expr): s.exclu = expr; return s
    def values(s, *a): return s
    def none(s): return s
    def all(s): return s


def cibles():  # ALLOWED_TARGETS = union des record_targets des platform.py (ARC30)
    sortie = set()
    for f in sorted((DJ / "apps").glob("*/platform.py")):
        for d in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            for k, val in zip(getattr(d, "keys", []), getattr(d, "values", [])):
                if isinstance(k, ast.Constant) and k.value == "record_targets": sortie |= {tuple(t.split(".", 1)) for t in ast.literal_eval(val)}
    return sortie


def sonde(ctx=None):
    R, P, comptes = noyau()
    ecrits = []
    ns = {"Comment": NS(objects=NS(create=lambda **k: ecrits.append(k))), "BonCommandeFournisseur": type("BonCommandeFournisseur", (), {}), "logger": NS(info=print),
          "ContentType": NS(objects=NS(get_for_model=lambda m: m.__name__))}
    ligne = "Ligne 9 — prix_achat_unitaire : Decimal('100.00') → Decimal('120.00')"  # forme construite par reviser_bcf (l'ast ci-dessous vérifie le champ)
    reel("apps/stock/services.py", "_log_revision_change", None, ns)("societe", NS(revision=2, pk=5), "u", [ligne])
    champ_prix = "prix_achat_unitaire" in ast.unparse(noeud("apps/stock/services.py", "_valider_revision_ligne_bcf"))
    frais = "coût moyen pondéré" in ast.unparse(noeud("apps/stock/services.py", "definir_frais_annexes_ligne_bcf"))
    label = "apps.achats".split(".")[-1] if "name = 'apps.achats'" in (DJ / "apps/achats/apps.py").read_text(encoding="utf-8") else "?"
    bcf_dans_achats = "BonCommandeFournisseur" in (DJ / "apps/achats/models.py").read_text(encoding="utf-8") and "app_label" not in (DJ / "apps/achats/models.py").read_text(encoding="utf-8")
    liste = passent(comptes, gardes(P, "apps/records/views.py", "CommentViewSet", "list"), vue("apps/records/views.py"))
    qs = QS(); excl = {}
    for nom in liste:
        u = comptes[nom]; ns2 = {"models": NS(Q=Q), "ALLOWED_TARGETS": cibles(), "MODULE_DES_APPS": P["MODULE_DES_APPS"], "codes_du_module": P["codes_du_module"],
                                 "ContentType": NS(objects=NS(get=lambda **k: NS(model_class=lambda: NS(objects=qs)))), "portee_leads": lambda q, user: q,
                                 "_user_has_or_legacy": lambda user, code: code in user.role.permissions}
        ns2["module_refuse"] = reel("apps/records/serializers.py", "module_refuse", None, ns2)
        reel("apps/records/views.py", "pieces_visibles", None, ns2)(qs, u, Q(author=u))
        excl[nom] = sorted({v for k, v in qs.exclu.f if k == "content_type__app_label"})
    lisent = [n for n in liste if "achats" not in excl[n] and "prix_achat_voir" not in comptes[n].role.permissions]
    return {"repro": bool(ecrits) and "prix_achat_unitaire" in ecrits[0]["body"] and champ_prix and bool(lisent), "observe": {
        "methode": "VRAIES get_permissions, pieces_visibles et module_refuse exécutées ; _log_revision_change exécutée sur Comment bouchonné",
        "ecrivain": {"commentaire_sur": ecrits[0]["content_type"], "corps": ecrits[0]["body"], "champ_prix_valide_par_reviser_bcf": champ_prix, "frais_annexes_ecrivent_le_PMP": frais},
        "bcf_dans_app_label": label if bcf_dans_achats else "?", "cibles_declarees_achats": sorted(c for c in cibles() if c[0] == "achats"),
        "route": "GET records/comments/ (sans model/id)", "code_attendu": "prix_achat_voir", "app_labels_exclus_par_role": excl, "roles_livres_qui_lisent_le_prix_sans_le_code": lisent}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
