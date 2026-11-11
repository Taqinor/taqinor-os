"""Fournisseur archivé, bloqué « total » ou rejeté : la porte à JETON le refuse (ASTK179), la porte COMPTE (JWT) non.
Exécute les vraies gardes (roles/permissions.py) et les vrais cœurs stock (selectors/services.py) sur des bouchons ORM."""
SONDE = {"constat": "C-APUB-037", "sha": "ae5a7ae4c",
         "attendu": "jeton → None pour les 3 états ; compte → permission True, BCF servis, date confirmée écrite"}
import ast, datetime, pathlib, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


def extraire(rel, noms, ns):
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8"))
    corps = [n for n in arbre.body if getattr(n, "name", None) in noms
             or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in noms for t in n.targets))]
    exec(compile(ast.Module(body=corps, type_ignores=[]), rel, "exec"), ns)
    return ns


class QS(list):
    def _ok(s, o, k, v): return True if "__" in k else getattr(o, k, None) == v
    def filter(s, **kw): return QS(o for o in s if all(s._ok(o, k, v) for k, v in kw.items()))
    def exclude(s, **kw): return QS(o for o in s if not all(s._ok(o, k, v) for k, v in kw.items()))
    def select_related(s, *a): return s
    prefetch_related = order_by = select_related
    def first(s): return s[0] if s else None
    def exists(s): return bool(s)
    def all(s): return s


class Fournisseur:
    class Statut: ACTIF, BLOQUE_TOTAL = "actif", "bloque_total"
    class StatutValidation: VALIDE, REJETE = "valide", "rejete"


class BonCommandeFournisseur:
    class Statut: BROUILLON, ANNULE, ENVOYE = "brouillon", "annule", "envoye"


class ReceptionFournisseur:
    class Statut: CONFIRME = "confirme"
    objects = QS()


def monde(etat):
    societe = types.SimpleNamespace(id=1)
    f = types.SimpleNamespace(pk=7, id=7, company=societe, is_archived=False, statut=Fournisseur.Statut.ACTIF,
                              statut_validation=Fournisseur.StatutValidation.VALIDE)
    setattr(f, *etat)
    bc = types.SimpleNamespace(pk=40, id=40, company=societe, fournisseur=f, fournisseur_id=7, reference="BCF-2611-001",
                               statut="envoye", date_commande=None, date_livraison_prevue=datetime.date(2026, 12, 1),
                               date_confirmee_fournisseur=None, numero_confirmation_fournisseur="", lignes=QS(),
                               get_statut_display=lambda: "Envoyé", save=lambda **k: None)
    jeton = types.SimpleNamespace(token="t" * 43, est_valide=True, fournisseur=f, company=societe)
    Fournisseur.objects, BonCommandeFournisseur.objects = QS([f]), QS([bc])
    PortailFournisseurToken = type("PortailFournisseurToken", (), {"objects": QS([jeton])})
    sys.modules["_sonde_stock.models"].__dict__.update(
        Fournisseur=Fournisseur, BonCommandeFournisseur=BonCommandeFournisseur,
        ReceptionFournisseur=ReceptionFournisseur, PortailFournisseurToken=PortailFournisseurToken)
    user = types.SimpleNamespace(is_authenticated=True, portee="portail_fournisseur", portail_fournisseur_id=7,
                                 company=societe, company_id=1)
    return societe, f, bc, user


def sonde(ctx=None):
    poses = {"_sonde_stock": types.ModuleType("_sonde_stock"), "_sonde_stock.models": types.ModuleType("_sonde_stock.models"),
             "django": types.ModuleType("django"), "django.utils": types.ModuleType("django.utils"),
             "django.utils.dateparse": types.ModuleType("django.utils.dateparse")}
    poses["_sonde_stock"].__path__ = []
    poses["django.utils.dateparse"].parse_date = lambda s: datetime.date.fromisoformat(s) if s else None
    avant = {k: sys.modules.get(k) for k in poses}
    sys.modules.update(poses)
    try:
        perm = extraire("apps/roles/permissions.py", {"PORTEE_INTERNE", "PORTAL_SCOPE_FIELDS", "is_portal_user",
                        "portal_scope_id", "acces_portail_revoque", "_IsPortalUserOfScope", "IsPortalFournisseurUser"},
                        {"BasePermission": object, "exiger_mot_de_passe_change": lambda u: None})
        sel = extraire("apps/stock/selectors.py", {"bcf_portail_fournisseur"}, {"__package__": "_sonde_stock"})
        svc = extraire("apps/stock/services.py", {"resoudre_token_portail_fournisseur", "MSG_CONFIRMATION_BCF_REFUSEE",
                       "ConfirmationBcfRefusee", "ConfirmationBcfInvalide", "NUMERO_CONFIRMATION_MAX",
                       "_valider_confirmation_bcf", "bcf_confirmable_par_fournisseur",
                       "_appliquer_confirmation_bcf_fournisseur"}, {"__package__": "_sonde_stock"})
        resultats, defaut = {}, False
        for nom, etat in (("archivé", ("is_archived", True)), ("bloqué total", ("statut", Fournisseur.Statut.BLOQUE_TOTAL)),
                          ("rejeté", ("statut_validation", Fournisseur.StatutValidation.REJETE))):
            societe, f, bc, user = monde(etat)
            jeton = svc["resoudre_token_portail_fournisseur"]("t" * 43)
            ok = perm["IsPortalFournisseurUser"]().has_permission(types.SimpleNamespace(user=user, method="GET"), None)
            bcfs = sel["bcf_portail_fournisseur"](societe, perm["portal_scope_id"](user))
            try:
                svc["_appliquer_confirmation_bcf_fournisseur"](societe, 7, 40, date_confirmee=datetime.date(2027, 1, 15))
                confirme = bc.date_confirmee_fournisseur
            except ValueError as exc:
                confirme = f"refusé : {exc}"
            resultats[nom] = {"porte_jeton (resoudre_token_portail_fournisseur)": "refusé" if jeton is None else "ouvert",
                              "porte_compte IsPortalFournisseurUser.has_permission": ok,
                              "mes-bcf (bcf_portail_fournisseur)": [b["reference"] for b in bcfs],
                              "mes-bcf/<id>/confirmer (_appliquer_confirmation_bcf_fournisseur)": str(confirme)}
            defaut = defaut or (jeton is None and ok and bool(bcfs) and isinstance(confirme, datetime.date))
    finally:
        for k, v in avant.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v
    appelants = sorted(str(p.relative_to(DJ)).replace("\\", "/") for p in DJ.rglob("*.py")
                       if "compte_fournisseur_portail_actif(" in p.read_text(encoding="utf-8", errors="ignore")
                       and "test" not in p.name and "migrations" not in p.parts)
    arbre = ast.parse((DJ / "apps/stock/services.py").read_text(encoding="utf-8"))
    bascule = next(n for n in arbre.body if getattr(n, "name", "") == "_basculer_acces_compte_fournisseur")
    noms = {n.id for n in ast.walk(bascule) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(bascule) if isinstance(n, ast.Attribute)}
    return {"repro": defaut, "observe": {
        "methode": "exécution des vraies fonctions (ast + bouchons ORM) ; ShareLink et appelants par ast",
        "par_etat_du_fournisseur": resultats,
        "appelants hors tests de stock.selectors.compte_fournisseur_portail_actif": appelants,
        "_basculer_acces_compte_fournisseur coupe les ShareLink public/bcf/<t>/": "ShareLink" in noms,
        "routes": "GET portail/fournisseur/mes-bcf/, POST mes-bcf/<id>/confirmer/, tableau de bord fournisseur",
        "note": "bouchons : _ok ignore les lookups '__' ; ReceptionFournisseur vide (BCF non reçu)"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
