"""Tests CONTRAT16 — SignatureContrat (signature e-sign IN-APP + statut signé).

Couvre :
- La signature enregistre les preuves (nom dactylographié, rôle, IP, user agent,
  méthode, utilisateur agissant).
- Le contrat bascule à ``signe`` quand TOUTES les parties requises (client +
  prestataire) ont signé — via la machine d'états gardée, jamais un funnel
  STAGES.py.
- Une signature PARTIELLE (une seule partie) ne fait PAS basculer le statut.
- Le rôle « témoin » seul ne fait pas basculer ; une 2nde signature du même rôle
  est refusée (gate de doublon).
- La bascule ne se produit pas depuis un état documentaire incompatible
  (préservation des statuts — CONTRAT12).
- Multi-tenant : signatures scopées société ; endpoints scopés société.
- Utilisateur agissant + société posés CÔTÉ SERVEUR (jamais lus du corps).
- Endpoints : signer / lister (+ accès réservé au palier admin/responsable).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import (
    Contrat,
    PartieContrat,
    SignatureContrat,
)

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_contrat(company, statut="en_approbation", objet="Contrat test",
                 avec_parties=True):
    """Contrat prêt à signer : en approbation + 2 parties (client/prestataire).

    Le statut par défaut ``en_approbation`` + 2 parties autorise la transition
    gardée ``en_approbation → signe`` de la machine d'états.
    """
    contrat = Contrat.objects.create(
        company=company, objet=objet, montant=Decimal("80000"),
        type_contrat="vente", statut=statut)
    if avec_parties:
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="client", nom="Client SARL", ordre=0)
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="prestataire", nom="Taqinor", ordre=1)
    return contrat


# ---------------------------------------------------------------------------
# Service — enregistrement de la signature + preuves
# ---------------------------------------------------------------------------

class SignerServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("sig-svc", "SigSvc")
        self.user = make_user(self.co, "sig-svc-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_signature_enregistre_les_preuves(self):
        res = services.signer_contrat(
            self.contrat,
            signataire_nom="  Ahmed Benani  ",
            role_signataire="client",
            signataire=self.user,
            ip_adresse="41.92.10.5",
            user_agent="Mozilla/5.0 (X11; Linux) Test",
            auteur=self.user,
        )
        sig = res["signature"]
        self.assertEqual(sig.signataire_nom, "Ahmed Benani")  # strippé
        self.assertEqual(sig.role_signataire, "client")
        self.assertEqual(sig.signataire_id, self.user.id)
        self.assertEqual(sig.ip_adresse, "41.92.10.5")
        self.assertIn("Mozilla", sig.user_agent)
        self.assertEqual(sig.methode, SignatureContrat.Methode.TYPED)
        self.assertEqual(sig.company_id, self.co.id)
        self.assertIsNotNone(sig.date_signature)

    def test_nom_vide_refuse(self):
        with self.assertRaises(services.SignatureError):
            services.signer_contrat(
                self.contrat, signataire_nom="   ",
                role_signataire="client")

    def test_methode_draw_acceptee(self):
        res = services.signer_contrat(
            self.contrat, signataire_nom="X", role_signataire="client",
            methode=SignatureContrat.Methode.DRAW)
        self.assertEqual(res["signature"].methode, "draw")

    def test_signataire_externe_sans_compte(self):
        # Une partie externe signe sans utilisateur ERP : signataire = None.
        res = services.signer_contrat(
            self.contrat, signataire_nom="Client externe",
            role_signataire="client", signataire=None)
        self.assertIsNone(res["signature"].signataire_id)


# ---------------------------------------------------------------------------
# Service — bascule de statut (complète / partielle / incompatible)
# ---------------------------------------------------------------------------

class BasculeStatutTests(TestCase):
    def setUp(self):
        self.co = make_company("sig-basc", "Bascule")
        self.user = make_user(self.co, "sig-basc-admin", role="admin")

    def test_bascule_signe_quand_toutes_parties_signent(self):
        contrat = make_contrat(self.co)
        services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client")
        contrat.refresh_from_db()
        # Signature partielle : pas encore basculé.
        self.assertEqual(contrat.statut, "en_approbation")

        res = services.signer_contrat(
            contrat, signataire_nom="Presta", role_signataire="prestataire")
        contrat.refresh_from_db()
        self.assertTrue(res["contrat_signe"])
        self.assertEqual(contrat.statut, Contrat.Statut.SIGNE)

    def test_signature_partielle_ne_bascule_pas(self):
        contrat = make_contrat(self.co)
        res = services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client")
        contrat.refresh_from_db()
        self.assertFalse(res["contrat_signe"])
        self.assertEqual(contrat.statut, "en_approbation")
        self.assertFalse(services.toutes_parties_signataires(contrat))

    def test_temoin_seul_ne_bascule_pas(self):
        contrat = make_contrat(self.co)
        services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client")
        res = services.signer_contrat(
            contrat, signataire_nom="Témoin", role_signataire="temoin")
        contrat.refresh_from_db()
        # Client + témoin ≠ parties requises (client + prestataire).
        self.assertFalse(res["contrat_signe"])
        self.assertEqual(contrat.statut, "en_approbation")

    def test_doublon_role_refuse(self):
        contrat = make_contrat(self.co)
        services.signer_contrat(
            contrat, signataire_nom="Client A", role_signataire="client")
        with self.assertRaises(services.SignatureError):
            services.signer_contrat(
                contrat, signataire_nom="Client B", role_signataire="client")
        # Une seule signature client conservée.
        self.assertEqual(
            contrat.signatures.filter(role_signataire="client").count(), 1)

    def test_pas_de_bascule_depuis_etat_incompatible(self):
        # Un contrat en ``brouillon`` n'autorise PAS la transition → signe
        # (machine d'états : brouillon → {en_approbation, resilie}). La
        # signature est enregistrée mais le statut est PRÉSERVÉ.
        contrat = make_contrat(self.co, statut="brouillon")
        services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client")
        res = services.signer_contrat(
            contrat, signataire_nom="Presta", role_signataire="prestataire")
        contrat.refresh_from_db()
        self.assertFalse(res["contrat_signe"])
        self.assertEqual(contrat.statut, "brouillon")
        # Les deux signatures restent enregistrées (préservation des statuts).
        self.assertEqual(contrat.signatures.count(), 2)

    def test_bascule_journalisee_dans_le_chatter(self):
        contrat = make_contrat(self.co)
        services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        services.signer_contrat(
            contrat, signataire_nom="Presta", role_signataire="prestataire",
            auteur=self.user)
        # Chatter (CONTRAT15) : 2 entrées « signature » + 1 entrée « statut ».
        champs = list(
            contrat.activites.values_list("field", flat=True))
        self.assertEqual(champs.count("signature"), 2)
        self.assertEqual(champs.count("statut"), 1)


# ---------------------------------------------------------------------------
# Multi-tenant
# ---------------------------------------------------------------------------

class SignatureTenantTests(TestCase):
    def setUp(self):
        self.a = make_company("sig-a", "A")
        self.b = make_company("sig-b", "B")
        self.contrat_a = make_contrat(self.a)
        self.contrat_b = make_contrat(self.b)
        services.signer_contrat(
            self.contrat_a, signataire_nom="A", role_signataire="client")
        services.signer_contrat(
            self.contrat_b, signataire_nom="B", role_signataire="client")

    def test_signatures_scopees_societe(self):
        sigs_a = selectors.signatures_contrat(self.contrat_a)
        for s in sigs_a:
            self.assertEqual(s.company_id, self.a.id)
        ids_b = set(
            self.contrat_b.signatures.values_list("id", flat=True))
        ids_a = set(sigs_a.values_list("id", flat=True))
        self.assertFalse(ids_a & ids_b)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class SignatureEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("sig-ep", "EP")
        self.admin = make_user(self.co, "sig-ep-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def _url(self, suffix):
        return f"{CONTRATS}{self.contrat.id}/{suffix}/"

    def test_signer_endpoint_pose_user_et_preuves_serveur(self):
        api = auth(self.admin)
        resp = api.post(
            self._url("signer"),
            {"signataire_nom": "Reda", "role_signataire": "client"},
            format="json",
            HTTP_USER_AGENT="pytest-agent/1.0",
            REMOTE_ADDR="10.0.0.7",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        sig = SignatureContrat.objects.get(
            contrat=self.contrat, role_signataire="client")
        # Utilisateur agissant + preuves posés CÔTÉ SERVEUR (jamais du corps).
        self.assertEqual(sig.signataire_id, self.admin.id)
        self.assertEqual(sig.ip_adresse, "10.0.0.7")
        self.assertEqual(sig.user_agent, "pytest-agent/1.0")
        self.assertFalse(resp.data["contrat_signe"])

    def test_signer_les_deux_parties_bascule_signe(self):
        api = auth(self.admin)
        api.post(
            self._url("signer"),
            {"signataire_nom": "Client", "role_signataire": "client"},
            format="json")
        resp = api.post(
            self._url("signer"),
            {"signataire_nom": "Presta", "role_signataire": "prestataire"},
            format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["contrat_signe"])
        self.assertEqual(resp.data["statut"], "signe")
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "signe")

    def test_signer_doublon_400(self):
        api = auth(self.admin)
        api.post(
            self._url("signer"),
            {"signataire_nom": "Client A", "role_signataire": "client"},
            format="json")
        resp = api.post(
            self._url("signer"),
            {"signataire_nom": "Client B", "role_signataire": "client"},
            format="json")
        self.assertEqual(resp.status_code, 400)

    def test_signer_nom_vide_400(self):
        api = auth(self.admin)
        resp = api.post(
            self._url("signer"),
            {"signataire_nom": "   ", "role_signataire": "client"},
            format="json")
        self.assertEqual(resp.status_code, 400)

    def test_lister_signatures(self):
        api = auth(self.admin)
        api.post(
            self._url("signer"),
            {"signataire_nom": "Client", "role_signataire": "client"},
            format="json")
        resp = api.get(self._url("signatures"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["role_signataire"], "client")
        # user_agent n'est pas lu du corps : exposé en lecture seule.
        self.assertIn("user_agent", resp.data[0])

    def test_signer_autre_societe_404(self):
        autre = make_company("sig-ep-autre", "Autre")
        contrat_autre = make_contrat(autre)
        api = auth(self.admin)
        resp = api.post(
            f"{CONTRATS}{contrat_autre.id}/signer/",
            {"signataire_nom": "X", "role_signataire": "client"},
            format="json")
        # Le contrat n'appartient pas à la société de l'utilisateur → 404.
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co, "sig-ep-normal", role="commercial")
        api = auth(normal)
        resp = api.post(
            self._url("signer"),
            {"signataire_nom": "X", "role_signataire": "client"},
            format="json")
        self.assertEqual(resp.status_code, 403)
