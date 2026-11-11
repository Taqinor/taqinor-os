"""Rejoue le circuit de signature GED : (1) VRAIES gardes de lecture des deux viewsets + VRAI get_lien_signature : le jeton sort à tout compte interne ; (2) VRAIES fonctions de services.py de la route publique mono : le jeton GLOBAL signe une demande à destinataires, sans OTP ; (3) la voie destinataire refuse sans OTP ; (4) le rejeu est refusé."""
SONDE = {"constat": "C-ALEC-001", "sha": "ae5a7ae4c",
         "attendu": "jeton/lien servi sans masque à tous les rôles internes (même sans code ged) ; le jeton global d'une demande à 2 destinataires OTP la passe à « signe » (destinataires non signés, otp_valide faux) ; voie destinataire sans OTP refusée ; rejeu refusé"}
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


SVC, VUES, SERS = "apps/ged/services.py", "apps/ged/views.py", "apps/ged/serializers.py"


class QS(list):
    def select_related(self, *a): return self
    def filter(self, **kw): return QS(o for o in self if all(getattr(o, k) == v for k, v in kw.items()))
    def first(self): return self[0] if self else None
    def all(self): return self


class Obj(NS):
    def save(self, update_fields=None): pass


def sonde(ctx=None):
    R, P, comptes = noyau()
    # (1) qui lit, quels champs sortent
    r1 = passent(comptes, gardes(P, VUES, "DemandeSignatureDocumentViewSet", "list"), vue(VUES))
    g2 = [P[ast.unparse(e)]() for e in noeud(VUES, "permission_classes", "SignataireDemandeViewSet").value.elts]
    lisent = sorted(set(r1) & set(passent(comptes, g2, vue(VUES))))
    sans_ged = [n for n in lisent if not any(c.startswith("ged_") for c in comptes[n].role.permissions)]
    ns_u = {"settings": NS(PUBLIC_BASE_URL="https://erp.exemple", CSRF_TRUSTED_ORIGINS=[]), "logger": NS(warning=print)}
    url = reel(SVC, "url_publique_signature", None, ns_u)
    lien = reel(SERS, "get_lien_signature", "SignataireDemandeSerializer", {"services": NS(url_publique_signature=url)})(NS(context={}), NS(token="JETON-DU-DESTINATAIRE"))
    champs = ast.literal_eval(next(b for b in noeud(SERS, "Meta", "DemandeSignatureDocumentSerializer").body if getattr(b.targets[0], "id", "") == "fields").value)
    masque = any(getattr(b, "name", "") == "to_representation" for n in ("DemandeSignatureDocumentSerializer", "SignataireDemandeSerializer") for b in noeud(SERS, n).body)
    jeton_servi = "token" in champs and "JETON-DU-DESTINATAIRE" in lien and not masque
    # (2)-(4) la route publique mono : VRAIES fonctions de services.py, ORM bouchonné
    demandes, effets = QS(), []
    ns = {**constantes("apps/ged/models.py"), **{k: v for k, v in constantes(SVC).items() if k.startswith("SIGNATURE_PUBLIQUE")}, "DemandeSignatureDocument": NS(objects=demandes),
          "timezone": NS(now=lambda: "2026-11-11"), "logging": NS(getLogger=lambda n: NS(info=print, warning=print)), "json": __import__("json"),
          "selectors_latest_version": lambda d: None, "_hash_version_contenu": lambda v: "", "enregistrer_valeurs_champs": lambda *a, **k: None, "notifier_prochains_signataires": lambda d: None,
          "figer_pdf_signe": lambda d: effets.append("pdf_signe_fige"), "classer_signature_completee": lambda d: effets.append("certificat_depose"),
          "journaliser_evenement": lambda doc, **k: effets.append("journal"), "champs_du_signataire": lambda s: []}
    for f in ("resolve_signature_publique", "signer_demande_publique_avec_champs", "signer_demande_publique", "_poser_preuves_signature", "_normaliser_valeurs_champs",
              "_verifier_champs_requis", "marquer_signe", "signer_signataire", "_maj_statut_global"): reel(SVC, f, None, ns)

    def demande(pk, token, signataires=()):
        o = Obj(pk=pk, token=token, statut="en_attente", expires_at=None, is_expired=False, document=Obj(pk=10 + pk, nom="Contrat"), signataire_nom="Client", champs=QS(),
                signataires=QS(signataires), date_signature=None, provider_ref="", consentement_explicite=False, hash_contenu="")
        demandes.append(o); return o

    def appel_public(token):  # ordre de views.public_signature (POST action=signer)
        st, d = ns["resolve_signature_publique"](token)
        return st, (ns["signer_demande_publique_avec_champs"](d, consentement=True, signature_texte="Client", signature_tracee="", adresse_ip="10.0.0.5", user_agent="x", valeurs_champs=None) if st == "ok" else d)

    dest = lambda n, st: Obj(nom=n, statut=st, role="signataire", auth_extra="sms", otp_valide=False, otp_degrade=False, otp_requis_et_non_valide=True)
    s1, s2 = dest("A", "notifie"), dest("B", "en_attente")
    demande(1, "JETON-MONO"); multi = demande(2, "JETON-GLOBAL-MULTI", [s1, s2])
    st_mono, d_mono = appel_public("JETON-MONO")
    st_multi, d_multi = appel_public("JETON-GLOBAL-MULTI")
    try: ns["signer_signataire"](s1, consentement=True, signature_texte="x"); voie_dest = "ACCEPTEE sans OTP"
    except ValueError as e: voie_dest = f"refusée : {e}"
    rejeu = ns["resolve_signature_publique"]("JETON-MONO")[0]
    refus_destinataires = any("signataires" in ast.unparse(noeud(c, f)) for c, f in ((VUES, "public_signature"), (SVC, "resolve_signature_publique")))
    multi_signee = d_multi.statut == "signe" and not any(s.otp_valide for s in (s1, s2)) and not refus_destinataires
    return {"repro": bool(jeton_servi or multi_signee), "observe": {
        "methode": "VRAIES get_permissions, get_lien_signature et fonctions de la route publique (resolve/signer/marquer_signe/signer_signataire) exécutées ; Meta.fields lus par ast",
        "jeton_servi_a_tout_interne": {"routes": ["GET ged/demandes-signature/", "GET ged/signataires-demande/"], "roles_livres_qui_lisent": lisent, "dont_sans_aucun_code_ged": sans_ged,
                                       "token_dans_les_champs": "token" in champs, "masque_dans_les_serialiseurs": masque, "lien_servi": lien},
        "route_mono_signe_une_demande_a_destinataires": {"mono": f"resolve={st_mono} -> {d_mono.statut}", "multi_par_jeton_global": f"resolve={st_multi} -> {d_multi.statut}",
                                                        "destinataires": [(s.nom, s.statut, f"otp_valide={s.otp_valide}") for s in (s1, s2)], "effets": effets, "refus_si_destinataires": refus_destinataires},
        "voie_destinataire_sans_otp": voie_dest, "rejeu_du_jeton_mono": rejeu}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
