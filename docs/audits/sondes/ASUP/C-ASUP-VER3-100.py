"""Rejoue crm/dsr_provider.py::anonymiser_client sur un client dont la facture émise est FIGÉE (AARG27, ASUP1-3), puis
exécute les VRAIS corps de ventes/exports.py::_compta_rows, ::lignes_rectificatives et ::pieces_rectificatives (export
comptable xlsx/csv ; mêmes colonnes « Client » / « ICE client » que export_journal_ventes et _grand_livre_rows_reconstitues,
relus) avec un ORM bouchonné. La facture, son avoir et sa note de débit sortent sous « Client anonymisé #N », ICE vide,
alors que acheteur_de_la_facture(facture) garde « SARL Exemple » et son ICE (ce que le PDF imprime depuis ASUP57)."""
SONDE = {"constat": "C-ASUP-VER3-100", "sha": "a12f40f82",
         "attendu": "après « Anonymiser (RGPD) », l'export comptable (et le journal des ventes, le grand livre reconstitué) "
                    "listent la facture, l'avoir et la note de débit émis sous le client vivant anonymisé, ICE vide, "
                    "alors que l'acheteur figé de la facture (PDF) garde nom et ICE"}
import ast, pathlib, sys, types
from decimal import Decimal, ROUND_HALF_UP
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"
ICE = "000000000000001"


def extraire(fichier, noms):  # CORPS RÉELS des fonctions nommées
    arbre = ast.parse((DJ / fichier).read_text(encoding="utf-8"))
    garde = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in noms]
    assert {n.name for n in garde} == set(noms), (fichier, [n.name for n in garde])
    return compile(ast.Module(body=garde, type_ignores=[]), fichier, "exec")


def lit_client_vivant(fichier, fonction):  # le VRAI corps lit-il getattr(<x>.client, 'ice') ?
    arbre = ast.parse((DJ / fichier).read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == fonction)
    return any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "getattr" and len(n.args) >= 2
               and isinstance(n.args[0], ast.Attribute) and n.args[0].attr == "client"
               and isinstance(n.args[1], ast.Constant) and n.args[1].value == "ice" for n in ast.walk(f))


class QS(list):  # chaîne ORM minimale
    def filter(self, **k): return self
    def select_related(self, *a): return self
    def prefetch_related(self, *a): return self
    def order_by(self, *a): return self


class Client:
    def __init__(self):
        self.id = self.pk = 12
        self.nom, self.prenom, self.type_client = "SARL Exemple", None, "entreprise"
        self.ice, self.if_fiscal, self.rc = ICE, "0000001", "RC 0001"
        self.adresse, self.email, self.telephone = "1 rue Exemple", "x@example.invalid", "+212600000000"
        self.cin, self.custom_data, self.is_anonymized, self.anonymized_at, self.tiers_id = None, {}, False, None, 7

    def save(self, update_fields=None): pass


class Facture:
    def __init__(self, client):
        self.client, self.client_id, self.company = client, client.id, "societe"
        self.identite_acheteur, self.statut, self.devis_id = None, "emise", None
        self.reference, self.date_emission, self.type_facture = "FAC-2026-11-0001", None, "complete"

    def get_type_facture_display(self): return "Facture"


class Piece:  # Avoir / NoteDebit émis : FK client + FK facture, aucun instantané d'acheteur (modèles relus)
    def __init__(self, client, facture, reference):
        self.client, self.facture, self.facture_id, self.reference = client, facture, 1, reference
        self.date_emission = None
        self.tva_par_taux = [{"taux": 20, "base_ht": Decimal("100"), "montant": Decimal("20")}]


def sonde(ctx=None):
    for nom in ("apps", "apps.tiers", "apps.ventes", "apps.ventes.utils", "apps.facturation"):
        sys.modules.setdefault(nom, types.ModuleType(nom))
    m_lib = types.ModuleType("apps.ventes.utils.libelles_ar")
    m_lib.document_langue = lambda client, company=None: "fr"
    sys.modules["apps.ventes.utils.libelles_ar"] = m_lib
    m_tiers = types.ModuleType("apps.tiers.services")
    m_tiers.CHAMPS_PERSONNE, m_tiers.anonymiser_tiers = ("nom",), (lambda company, tid, champs: None)
    m_fac = types.ModuleType("apps.facturation.services")  # facture déjà figée : rien à figer
    m_fac.figer_identite_acheteur_manquante = lambda company, client_id=None, appliquer=False: ([], [])
    sys.modules.update({"apps.tiers.services": m_tiers, "apps.facturation.services": m_fac})

    ns = {"timezone": types.SimpleNamespace(now=lambda: "2026-11-14T12:00"), "Decimal": Decimal, "ROUND_HALF_UP": ROUND_HALF_UP,
          "ISSUED_STATUTS": ("emise", "payee", "en_retard")}
    exec(extraire("apps/crm/dsr_provider.py", ["anonymiser_client"]), ns)
    exec(extraire("apps/ventes/domain/instantanes_facture.py",
                  ["acheteur_de_la_facture", "identite_acheteur_courante", "figer_a_l_emission"]), ns)
    exec(extraire("apps/ventes/exports.py",
                  ["_q2", "_compta_rows", "lignes_rectificatives", "pieces_rectificatives"]), ns)
    ns["lignes_ventilees"] = lambda f: [(types.SimpleNamespace(designation="Centrale", quantite=1, prix_unitaire=100),
                                         Decimal("20"), Decimal("100"), Decimal("20"))]

    cl = Client()
    fac = Facture(cl)
    ns["figer_a_l_emission"](fac)  # émise : instantané figé (AARG27)
    av, nd = Piece(cl, fac, "AV-2026-11-0001"), Piece(cl, fac, "ND-2026-11-0001")
    m_mod = types.ModuleType("apps.ventes.models")
    statut = types.SimpleNamespace(EMISE="emis")
    m_mod.Facture = types.SimpleNamespace(objects=QS([fac]))
    m_mod.Avoir = types.SimpleNamespace(objects=QS([av]), Statut=statut)
    m_mod.NoteDebit = types.SimpleNamespace(objects=QS([nd]), Statut=statut)
    sys.modules["apps.ventes.models"] = m_mod

    temoin = [r[3:5] for r in ns["_compta_rows"]("societe", None, None)[0]]  # avant : nom + ICE d'origine
    ns["anonymiser_client"]("societe", cl, nom=f"Client anonymisé #{cl.id}", motif="sonde")
    fige = ns["acheteur_de_la_facture"](fac)
    apres = {r[0]: r[3:5] for r in ns["_compta_rows"]("societe", None, None)[0]}
    lecteurs = {f: lit_client_vivant("apps/ventes/exports.py", f) for f in
                ("export_journal_ventes", "_compta_rows", "lignes_rectificatives", "_grand_livre_rows_reconstitues")}
    repro = bool(all(t == ["SARL Exemple", ICE] for t in temoin)
                 and fige.nom == "SARL Exemple" and fige.ice == ICE
                 and all(v == [f"Client anonymisé #{cl.id}", ""] for v in apres.values()) and len(apres) == 3
                 and all(lecteurs.values()))
    return {"repro": repro, "observe": {
        "geste": "Anonymiser (RGPD) sur la fiche client, puis Ventes > exports : journal des ventes, export comptable, grand livre",
        "temoin_avant_anonymisation": temoin,
        "acheteur_fige_de_la_facture": {"nom": fige.nom, "ice": fige.ice},
        "export_comptable_apres": apres,
        "fonctions_qui_lisent_le_client_vivant": lecteurs}}


if __name__ == "__main__":
    print(sonde())
