"""Rejoue crm/dsr_provider.py::anonymiser_client, puis rend les VRAIS gabarits templates/pdf/avoir.html et note_debit.html
avec le VRAI environnement Jinja2 (erp_agentique/jinja2.py::environment) et le contexte que pose
ventes/utils/pdf.py::generate_avoir_pdf / ::generate_note_debit_pdf. La facture d'origine est figée (AARG27, ASUP1-3) et
garde son acheteur ; l'avoir et la note de débit, sans instantané, impriment « Client anonymisé #N » sans ICE / IF / RC."""
SONDE = {"constat": "C-ASUP-VER2-101", "sha": "d64fa1e4e",
         "attendu": "après « Anonymiser (RGPD) », un avoir ou une note de débit (re)rendu sur une facture figée imprime le client "
                    "vivant anonymisé : nom remplacé, ICE/IF/RC/adresse absents ; la facture d'origine, elle, garde son acheteur"}
import ast, importlib.util, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
ICE, IF_, RC = "000000000000001", "0000001", "RC 0001"


def extraire(fichier, noms):  # CORPS RÉELS des fonctions nommées
    arbre = ast.parse((DJ / fichier).read_text(encoding="utf-8"))
    garde = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in noms]
    assert {n.name for n in garde} == set(noms), (fichier, [n.name for n in garde])
    return compile(ast.Module(body=garde, type_ignores=[]), fichier, "exec")


def cles_du_contexte(fichier, fonction):  # clés posées par `context['x'] = …` dans le VRAI corps
    arbre = ast.parse((DJ / fichier).read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == fonction)
    return sorted({c.slice.value for n in ast.walk(f) if isinstance(n, ast.Assign) for c in n.targets
                   if isinstance(c, ast.Subscript) and isinstance(c.value, ast.Name) and c.value.id == "context"
                   and isinstance(c.slice, ast.Constant)})


def _bouchons():
    figes = []
    for nom in ("apps", "apps.tiers", "apps.ventes", "apps.ventes.utils", "apps.facturation"):
        sys.modules.setdefault(nom, types.ModuleType(nom))
    m_tiers = types.ModuleType("apps.tiers.services")
    m_tiers.CHAMPS_PERSONNE = ("nom",)
    m_tiers.anonymiser_tiers = lambda company, tid, champs: None
    m_lib = types.ModuleType("apps.ventes.utils.libelles_ar")
    m_lib.document_langue = lambda client, company=None: "fr"
    m_fac = types.ModuleType("apps.facturation.services")  # la facture de la sonde est déjà figée : rien à figer
    m_fac.figer_identite_acheteur_manquante = lambda company, client_id=None, appliquer=False: figes.append(client_id) or ([], [])
    sys.modules.update({"apps.tiers.services": m_tiers, "apps.ventes.utils.libelles_ar": m_lib,
                        "apps.facturation.services": m_fac})
    return figes


class Vide:  # tout attribut non posé du document : vide, itérable, appelable (lignes, totaux…)
    def __getattr__(self, n): return Vide()
    def __call__(self, *a, **k): return Vide()
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __str__(self): return ""
    def __html__(self): return ""
    def __float__(self): return 0.0
    def __int__(self): return 0
    def __index__(self): return 0
    def __round__(self, n=0): return 0
    def __eq__(self, o): return isinstance(o, Vide) or o in (0, "", None)
    def __hash__(self): return 0
    def __lt__(self, o): return False
    def __gt__(self, o): return False
    def __len__(self): return 0
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = lambda self, o: 0


class Client:
    def __init__(self):
        self.id = self.pk = 12
        self.nom, self.prenom, self.type_client = "SARL Exemple", None, "entreprise"
        self.ice, self.if_fiscal, self.rc = ICE, IF_, RC
        self.adresse, self.email, self.telephone = "1 rue Exemple", "x@example.invalid", "+212600000000"
        self.cin, self.custom_data, self.is_anonymized, self.anonymized_at, self.tiers_id = None, {}, False, None, 7

    def save(self, update_fields=None): pass


class Facture:
    def __init__(self, client):
        self.client, self.client_id, self.company = client, client.id, "societe"
        self.identite_acheteur, self.statut, self.devis_id, self.reference = None, "emise", None, "FAC-2026-11-0001"


class Piece(Vide):  # Avoir / NoteDebit : FK client + FK facture, AUCUN champ identite_acheteur (modèles relus)
    def __init__(self, client, facture, reference):
        self.__dict__.update(client=client, facture=facture, reference=reference, statut="emis")


def rendre(env, gabarit, cle, piece):
    return env.get_template(gabarit).render({cle: piece, "entreprise_nom": "Vendeur", "couleur_principale": "#000",
                                             "langue_document": "fr"})


def sonde(ctx=None):
    figes = _bouchons()
    ns = {"timezone": types.SimpleNamespace(now=lambda: "2026-11-13T18:00")}
    exec(extraire("apps/crm/dsr_provider.py", ["anonymiser_client"]), ns)
    exec(extraire("apps/ventes/domain/instantanes_facture.py",
                  ["acheteur_de_la_facture", "identite_acheteur_courante", "figer_a_l_emission"]), ns)
    spec = importlib.util.spec_from_file_location("jinja_erp", DJ / "erp_agentique/jinja2.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    import jinja2
    env = mod.environment(loader=jinja2.FileSystemLoader(str(DJ / "templates/pdf")))

    cl = Client()
    fac = Facture(cl)
    ns["figer_a_l_emission"](fac)  # émise : instantané figé (AARG27)
    temoin = ICE in rendre(env, "avoir.html", "avoir", Piece(cl, fac, "AV-2026-11-0000"))  # avant : l'ICE est bien imprimé
    ns["anonymiser_client"]("societe", cl, nom=f"Client anonymisé #{cl.id}", motif="sonde")
    acheteur_facture = ns["acheteur_de_la_facture"](fac)
    html_av = rendre(env, "avoir.html", "avoir", Piece(cl, fac, "AV-2026-11-0001"))
    html_nd = rendre(env, "note_debit.html", "note_debit", Piece(cl, fac, "ND-2026-11-0001"))
    ctx_av = cles_du_contexte("apps/ventes/utils/pdf.py", "generate_avoir_pdf")
    ctx_nd = cles_du_contexte("apps/ventes/utils/pdf.py", "generate_note_debit_pdf")

    def lu(html):
        return {"nom_anonymise_imprime": "Client anonymisé #12" in html, "ice_d_origine_imprime": ICE in html,
                "if_imprime": IF_ in html, "rc_imprime": RC in html}
    av, nd = lu(html_av), lu(html_nd)
    facture_ok = acheteur_facture.nom == "SARL Exemple" and acheteur_facture.ice == ICE
    repro = bool(temoin and facture_ok and figes == [12]
                 and av["nom_anonymise_imprime"] and not av["ice_d_origine_imprime"]
                 and nd["nom_anonymise_imprime"] and not nd["ice_d_origine_imprime"]
                 and "acheteur" not in ctx_av and "acheteur" not in ctx_nd)
    return {"repro": repro, "observe": {
        "geste": "Anonymiser (RGPD) sur la fiche client, puis Créer un avoir / Annuler un avoir / Créer ou annuler une note de débit",
        "temoin_ice_imprime_avant_anonymisation": temoin,
        "facture_d_origine_figee": {"nom": acheteur_facture.nom, "ice": acheteur_facture.ice},
        "avoir_html": av, "note_debit_html": nd,
        "contexte_generate_avoir_pdf": ctx_av, "contexte_generate_note_debit_pdf": ctx_nd}}


if __name__ == "__main__":
    print(sonde())
