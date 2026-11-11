"""Rejoue notifications/signals.py::demande_achat_post_save : la VRAIE fonction exécutée sur une réquisition soumise (montant_estime = somme des prix d'achat estimés), destinataires = VRAIE sweeps._is_manager (est_manager réelle, palier réel) sur les rôles livrés ; on capture le corps envoyé à chacun."""
SONDE = {"constat": "C-ALEC-011", "sha": "ae5a7ae4c",
         "attendu": "le corps de la notification (in-app et e-mail) contient « Montant estimé : 1640.00 DH » pour des destinataires manager sans prix_achat_voir"}
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


def sonde(ctx=None):
    from decimal import Decimal
    R, P, comptes = noyau()
    sig = "apps/notifications/signals.py"; svc = "apps/notifications/services.py"
    paliers = runpy.run_path(str(DJ / "authentication/role_tiers.py"))["tier_for_role_fields"]
    ns_s = {"logger": NS(warning=lambda *a, **k: None), "palier_utilisateur": lambda u: paliers(u.role.nom, True, u.role.permissions)}
    est_manager = reel(svc, "est_manager", None, ns_s)
    managers = [c for c in comptes.values() if est_manager(c)]  # ce que _managers renvoie quand aucune règle de routage n'existe (APAR21)
    envois = []
    statut = NS(SOUMISE="soumise", APPROUVEE="a", REFUSEE="r")
    ns = {"_OLD_DA_STATUT_ATTR": "_old", "EventType": NS(APPROVAL_REQUESTED="approval_requested", APPROVAL_DECIDED="d"), "DemandeAchat": NS(Statut=statut),
          "_managers": lambda company, ev=None: managers, "resolve_recipients_reason": lambda c, e: "", "logger": NS(exception=print),
          "notify": lambda u, ev, titre, body="", **k: envois.append((u.role.nom, body))}
    inst = NS(statut="soumise", _old="brouillon", company="c", reference="DA-2611-0001", objet="Câbles", montant_estime=Decimal("1640.00"))
    reel(sig, "demande_achat_post_save", None, ns)(None, inst, created=False)
    recu = {nom: ("1640.00" in corps) for nom, corps in envois}
    fuient = [n for n, vu in recu.items() if vu and "prix_achat_voir" not in comptes[n].role.permissions]
    return {"repro": bool(fuient), "observe": {
        "methode": "VRAIES demande_achat_post_save et est_manager exécutées (notify capturé, ORM absent) ; montant_estime fixé à 1640.00",
        "evenement": "réquisition soumise (notification in-app + e-mail)", "code_attendu": "prix_achat_voir (jumeau d'ACHT16 / D-ACHT-90 : installations/services.py n'écrit le montant que si tous les destinataires le voient)",
        "corps_exemple": envois[0][1] if envois else None, "destinataires_managers": sorted(recu), "roles_livres_sans_le_code_qui_recoivent_le_montant": sorted(fuient)}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
