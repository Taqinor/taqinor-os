# flake8: noqa  (sonde HÔTE de contre-visite vérifie ASEC du 11/11/2026 — sans Django, sans base, sans Docker, rien écrit sur disque)
"""C-ASEC-VER7-096 — D-ASEC-VER6-1 (= exiger_encaisser : tout geste qui émet un avoir de contre-passation exige `encaisser`),
jumeau resté ouvert d'ASEC90 : `POST ventes/devis/<id>/facturer/` `{nature: complete, remplacer_brouillons: true}` SANS
`emettre`. Exécute (ast) la VRAIE garde (kwargs du vrai `@action` de `DevisFacturationActionsMixin.facturer` résolus par la vraie
`DevisViewSet.get_permissions` → `declared_action_permissions`, vraies classes d'`authentication/permissions.py`, vraies propriétés
de `CustomUser`), puis le VRAI corps `facturer` → `refus_avant_facturer` → `facturer_vente` → `_facturer_complete` →
`retirer_brouillons_de_la_vente` → `annuler_facture` → `_contre_passer`. Bouchons : ORM, verrou, plan de la vente, brouillon
complet, constructeur d'avoir (capture). Rôles LIVRÉS internes du registre vivant ; la vente porte UN brouillon remis
(référence légale). Témoins : `emettre: true` (403 sans `encaisser`) ; brouillon `BROUILLON-<id>` (201 sans avoir)."""
SONDE = {"constat": "C-ASEC-VER7-096", "sha": "42fb19c2c",
         "attendu": "Responsable et Admin Ventes (sans encaisser) : garde passée, 201, brouillon remis annulé et UN avoir de "
                    "contre-passation ; témoin emettre : 403 ; attendu sain : 403, aucun avoir"}
import ast, collections, contextlib, copy, json, pathlib, runpy, textwrap, types
from decimal import Decimal, ROUND_HALF_UP
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NS = types.SimpleNamespace

class _SansImport(ast.NodeTransformer):  # imports (même imbriqués) → pass : leurs noms viennent de l'espace fourni
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()

def _noeuds(rel, classe=None):
    arbre = ast.parse((DJ / rel).read_text(encoding="utf-8")).body
    return arbre if classe is None else next(n for n in arbre if isinstance(n, ast.ClassDef) and n.name == classe).body

def _nom(n): return getattr(n, "name", None) or (getattr(n.targets[0], "id", None) if isinstance(n, ast.Assign) else None)

def reel(rel, noms, ns, classe=None):  # exécute les nœuds RÉELS ``noms`` (du module, ou d'une classe) dans ``ns``
    pris = [_SansImport().visit(copy.deepcopy(n)) for n in _noeuds(rel, classe) if _nom(n) in noms]
    for n in pris:
        if classe and hasattr(n, "decorator_list"): n.decorator_list = []
    exec(compile(ast.fix_missing_locations(ast.Module(body=pris, type_ignores=[])), rel, "exec"), ns)

def kwargs_action(rel, classe, nom, ns):  # kwargs du VRAI décorateur @action, évalués avec les vraies gardes
    f = next(n for n in _noeuds(rel, classe) if _nom(n) == nom)
    d = next(d for d in f.decorator_list if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "action")
    return {k.arg: eval(compile(ast.Expression(k.value), rel, "eval"), ns) for k in d.keywords}

def utilisateur_reel():  # VRAIES propriétés de CustomUser
    cu = next(n for n in _noeuds("authentication/models.py") if isinstance(n, ast.ClassDef) and n.name == "CustomUser")
    src = "class Utilisateur:\n ROLE_ADMIN, ROLE_RESPONSABLE = 'admin', 'responsable'\n" + "".join(
        textwrap.indent(ast.unparse(f), " ") + "\n" for f in cu.body if isinstance(f, ast.FunctionDef)
        and f.name in ("is_responsable", "is_admin_role", "_role_grants_write", "has_erp_permission"))
    ns = {}; exec(src, ns); return ns["Utilisateur"]

class _Tout:  # bouchon permissif (traces, liens de paiement, événements)
    def __getattr__(s, n):
        if n[:2] == "__": raise AttributeError(n)
        return s
    def __call__(s, *a, **k): return s
    def __iter__(s): return iter(())
TOUT = _Tout()

class BasePermission:
    def has_permission(s, r, v): return True

def sonde(ctx=None):
    reg = runpy.run_path(str(DJ / "apps/roles/permissions_registre.py"))
    roles = [(n, set(p)) for n, p in reg["CANONICAL_SYSTEM_ROLES"] if n not in dict(reg["CANONICAL_PORTAIL_ROLES"])]
    st = next(n for n in _noeuds("apps/facturation/models.py", "Facture") if isinstance(n, ast.ClassDef) and n.name == "Statut")
    Statut = NS(**{n.targets[0].id: ast.literal_eval(n.value)[0] for n in st.body if isinstance(n, ast.Assign)})
    vente, avoirs, emissions = {}, [], []

    Facture = type("Facture", (NS,), {"Statut": Statut, "objects": NS(select_for_update=lambda: NS(get=lambda pk: vente[pk]))})

    def creer_avoir_facture(**k):  # capture ; le vrai constructeur (mode contre_passation) bascule la facture ANNULÉE
        k["facture"].statut = Statut.ANNULEE; avoirs.append((k["facture"].reference, k["mode"])); return NS(reference="AV-0001")
    ns = {"BasePermission": BasePermission, "SAFE_METHODS": ("GET", "HEAD", "OPTIONS"), "Decimal": Decimal,
          "ROUND_HALF_UP": ROUND_HALF_UP, "json": json, "transaction": NS(atomic=contextlib.nullcontext),
          "Response": lambda data=None, status=200, **k: NS(data=data, status_code=status),
          "status": NS(HTTP_403_FORBIDDEN=403, HTTP_201_CREATED=201), "D": TOUT, "valider_corps": lambda r, s: dict(r.data),
          "SaleWarningError": type("SaleWarningError", (Exception,), {}), "verifier_sale_warnings": lambda *a, **k: None,
          "_passe_outre": lambda u: False, "Facture": Facture, "Paiement": NS(STATUTS_NON_COMPTES=("rejete",)),
          "Avoir": NS(Type=NS(CORRECTION="correction")), "AvoirRefuse": type("AvoirRefuse", (Exception,), {}),
          "creer_avoir_facture": creer_avoir_facture, "notes_debit_actives": lambda f: [], "chaine_vente": lambda d: [d],
          "factures_de_la_vente": lambda d: list(vente.values()), "verrouiller_vente": lambda d: [d],
          "_exiger_vente_en_jeu": lambda d: None, "_montant_demande": lambda *a: None, "_paiements_saisis": lambda p: [],
          "plan_facturation": lambda d: {"prix_convenu_ttc": Decimal("1200"), "factures_parts": [(f, None) for f in vente.values()]},
          "_creer_brouillon_complet": lambda d, u, l: NS(pk=99, reference="BROUILLON-99", statut=Statut.BROUILLON,
                                                          total_ttc=Decimal("1200"), type_facture="complete"),
          "_emettre": lambda f, u, **k: emissions.append(f.pk), "_encaisser": lambda f, **k: [],
          "_retourner_stock_de_la_vente": lambda *a: None, "FactureActivity": TOUT, "PaymentLink": TOUT,
          "fermer_liens_paiement": TOUT, "facture_annulee": TOUT, "activity": TOUT,
          "etat_vente": lambda d, u: collections.defaultdict(str), "Devis": NS(objects=NS(get=lambda **k: None))}
    reel("authentication/permissions.py", {"_REGISTRE_MODULES", "_OCTROIS_LECTURE", "enregistrer_registre_modules",
         "_registre_modules", "APPS_SANS_MODULE", "MODULE_DES_APPS", "module_de_la_vue", "module_du_chemin",
         "peut_lire_module", "codes_du_module", "IsResponsableOrAdmin", "HasPermissionOrLegacy"}, ns)
    ns["enregistrer_registre_modules"](reg["PERMISSION_MODULE"], octrois_lecture=reg["OCTROIS_LECTURE"])  # = RolesConfig.ready()
    reel("core/permissions.py", {"declared_action_permissions"}, ns)
    reel("core/numbering.py", {"PREFIXE_PROVISOIRE", "est_reference_provisoire"}, ns)
    reel("apps/ventes/vente_facturation.py", {"STATUTS_EMIS", "STATUT_BROUILLON"}, ns)
    reel("apps/ventes/views/devis.py", {"get_permissions"}, ns, "DevisViewSet")
    reel("apps/ventes/views/devis_facturation.py", {"CLES_VENTE_FACTURER", "CHAMPS_FACTURER_VENTE", "_texte",
         "refus_avant_facturer"}, ns)
    reel("apps/ventes/views/devis_facturation.py", {"facturer"}, ns, "DevisFacturationActionsMixin")
    reel("apps/ventes/domain/facturation_vente.py", {"NATURES", "CENT", "FacturationVenteRefusee", "_q", "_conflit",
         "_facturer_complete", "facturer_vente"}, ns)
    reel("apps/ventes/domain/annulation_facture.py", {"GARDER_EN_AVANCE", "LIBELLE_TRACE_EFFETS", "AnnulationRefusee",
         "_refus_prealable", "_payes_hors_escompte", "_refuser_si_argent", "_contre_passer", "annuler_facture",
         "retirer_brouillons_de_la_vente"}, ns)
    ns["facturer"].kwargs = kwargs_action("apps/ventes/views/devis_facturation.py", "DevisFacturationActionsMixin", "facturer", ns)
    devis = NS(pk=1, id=1, company_id=1)
    Vue = type("DevisViewSet", (), {"__module__": "apps.ventes.views.devis", "permission_classes": [],
                                    "get_permissions": ns["get_permissions"], "facturer": ns["facturer"]})
    U = utilisateur_reel()

    def jouer(nom, perms, reference, corps):
        vente.clear(); avoirs.clear(); emissions.clear()
        vente[7] = Facture(pk=7, id=7, reference=reference, statut=Statut.BROUILLON, devis_id=1, company=NS(id=1),
                           montant_paye=Decimal("0"), total_ttc=Decimal("1200"), paiements=NS(all=lambda: []),
                           avoirs=NS(all=lambda: []), retenues_subies=TOUT, save=lambda **k: None,
                           refresh_from_db=lambda: None)
        u = U(); u.__dict__.update(is_superuser=False, is_authenticated=True, role_id=1, role_legacy="normal", company_id=1,
                                   role=NS(nom=nom, permissions=sorted(perms), est_systeme=True))
        v = Vue(); v.action, v.get_object = "facturer", lambda: devis
        req = NS(method="POST", user=u, data=corps)
        gardes = v.get_permissions()
        if not all(p.has_permission(req, v) for p in gardes):
            return {"http": 403, "garde": [type(p).__name__ for p in gardes], "avoirs": [], "brouillon": vente[7].statut}
        r = ns["facturer"](v, req, pk=1)
        return {"http": r.status_code, "garde": [type(p).__name__ for p in gardes], "avoirs": list(avoirs),
                "brouillon": vente[7].statut, "detail": (r.data or {}).get("detail")}
    remplacer = {"nature": "complete", "remplacer_brouillons": True}
    par_role = {n: jouer(n, p, "FAC-2026-11-0007", remplacer) for n, p in roles}
    sans_encaisser = {n for n, p in roles if "encaisser" not in p}
    a_tort = sorted(n for n in sans_encaisser if par_role[n]["http"] == 201 and par_role[n]["avoirs"])
    temoin_emettre = {n: jouer(n, p, "FAC-2026-11-0007", dict(remplacer, emettre=True))["http"] for n, p in roles if n in a_tort}
    av = dict(roles).get("Admin Ventes", set())
    temoin_provisoire = jouer("Admin Ventes", av, "BROUILLON-7", remplacer)
    return {"repro": bool(a_tort), "observe": {
        "methode": "exécution (ast) de la vraie garde + vrai corps facturer → refus_avant_facturer → facturer_vente → "
                   "_facturer_complete → retirer_brouillons_de_la_vente → annuler_facture → _contre_passer ; rôles du registre vivant",
        "route": "POST ventes/devis/<id>/facturer/ {nature: complete, remplacer_brouillons: true}", "droit_attendu": "encaisser",
        "roles_sans_encaisser_qui_emettent_l_avoir": a_tort, "temoin_emettre_http": temoin_emettre,
        "temoin_brouillon_provisoire": temoin_provisoire, "detail_par_role": par_role}}

if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
