"""Rejoue crm/dsr_provider.py::anonymiser_client puis ventes/domain/instantanes_facture.py::acheteur_de_la_facture : une facture émise SANS instantané identite_acheteur (toutes celles émises avant AARG27) imprime ensuite « Client anonymisé », sans ICE / IF / RC / adresse."""
SONDE = {"constat": "C-ASUP-001", "sha": "3acfee471",
         "attendu": "après « Anonymiser (RGPD) », l'acheteur d'une facture émise sans instantané perd son identité légale (nom remplacé, ICE/IF/RC/adresse vides)"}
import ast, pathlib, sys, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


def extraire(fichier, noms):  # CORPS RÉELS des fonctions nommées
    arbre = ast.parse((DJ / fichier).read_text(encoding="utf-8"))
    garde = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in noms]
    assert {n.name for n in garde} == set(noms), (fichier, [n.name for n in garde])
    return compile(ast.Module(body=garde, type_ignores=[]), fichier, "exec")


def _bouchons():
    appels = []
    m_tiers = types.ModuleType("apps.tiers.services")
    m_tiers.CHAMPS_PERSONNE = ("nom",)
    m_tiers.anonymiser_tiers = lambda company, tid, champs: appels.append(tid)
    m_lib = types.ModuleType("apps.ventes.utils.libelles_ar")
    m_lib.document_langue = lambda client, company=None: "fr"
    for nom in ("apps", "apps.tiers", "apps.ventes", "apps.ventes.utils"):
        sys.modules.setdefault(nom, types.ModuleType(nom))
    sys.modules["apps.tiers.services"] = m_tiers
    sys.modules["apps.ventes.utils.libelles_ar"] = m_lib
    return appels


class Client:
    def __init__(self):
        self.id, self.nom, self.prenom, self.type_client = 12, "SARL Exemple", None, "entreprise"
        self.ice, self.if_fiscal, self.rc = "000000000000001", "0000001", "RC 0001"
        self.adresse, self.email, self.telephone = "1 rue Exemple", "x@example.invalid", "+212600000000"
        self.cin, self.custom_data, self.is_anonymized, self.anonymized_at, self.tiers_id = None, {}, False, None, 7

    def save(self, update_fields=None):
        self.saved = update_fields


class Facture:
    def __init__(self, client):
        self.client, self.client_id, self.company = client, client.id, "societe"
        self.identite_acheteur, self.statut, self.devis_id = None, "emise", None


def sonde(ctx=None):
    _bouchons()
    ns = {"timezone": types.SimpleNamespace(now=lambda: "2026-11-11T10:00")}
    exec(extraire("apps/crm/dsr_provider.py", ["anonymiser_client"]), ns)
    exec(extraire("apps/ventes/domain/instantanes_facture.py",
                  ["acheteur_de_la_facture", "identite_acheteur_courante", "figer_a_l_emission"]), ns)
    cl = Client()
    sans, avec = Facture(cl), Facture(cl)
    ns["figer_a_l_emission"](avec)  # émise après AARG27 : instantané figé
    ns["anonymiser_client"]("societe", cl, nom=f"Client anonymisé #{cl.id}", motif="sonde")
    a, b = ns["acheteur_de_la_facture"](sans), ns["acheteur_de_la_facture"](avec)
    repro = bool(str(a.nom).startswith("Client anonymisé") and not a.ice)
    return {"repro": repro, "observe": {
        "geste": "Anonymiser (RGPD) sur la fiche client (ClientRgpdActions) ou demande d'effacement",
        "facture_sans_instantane": {"nom": a.nom, "ice": a.ice, "if": a.if_fiscal, "rc": a.rc, "adresse": a.adresse},
        "facture_avec_instantane": {"nom": b.nom, "ice": b.ice},
        "prod_lue_le_11_11": "10 factures émises/payées/en retard sur 10 sans instantané"}}


if __name__ == "__main__":
    print(sonde())
