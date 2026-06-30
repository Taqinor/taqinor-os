"""Tests CONTRAT31 — Lien facturation récurrente (via ventes).

Couvre :
- ``facturer_ligne_echeance`` émet une ``ventes.Facture`` (TTC ventilé HT/TVA),
  relie la facture à la ligne (``facture_id``) et journalise — sans toucher
  ``Contrat.statut``.
- Gardes : facturation non activée, échéance déjà facturée (idempotence),
  montant nul, contrat sans client → ``FacturationError``.
- Le client est résolu par ``crm.selectors`` (frontière cross-app).
- API : action ``facturer`` (201 + référence), refus 400 hors garde, scope/rôle.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes.models import Facture

from apps.contrats import services
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()

LIGNES = "/api/django/contrats/lignes-echeance/"


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


def make_setup(company, *, client=True, facturation_active=True,
               montant="1200"):
    cli = Client.objects.create(company=company, nom="Client SARL") if client \
        else None
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal("120000"),
        type_contrat="om", statut="actif",
        client_id=cli.id if cli else None,
        date_debut=timezone.localdate() - timedelta(days=10))
    ech = EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=facturation_active)
    ligne = services.ajouter_ligne_echeance(
        ech, date_echeance=timezone.localdate(), montant=Decimal(montant))
    return contrat, ech, ligne


class FacturationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("facrec-svc", "FacRecSvc")
        self.user = make_user(self.co, "facrec-svc-admin", role="admin")

    def test_facture_emise_et_reliee(self):
        contrat, ech, ligne = make_setup(self.co, montant="1200")
        facture = services.facturer_ligne_echeance(ligne, user=self.user)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(facture.montant_ttc, Decimal("1200.00"))
        self.assertEqual(facture.company_id, self.co.id)
        # TTC = 1200 → HT 1000, TVA 200 (20 %).
        self.assertEqual(facture.montant_ht, Decimal("1000.00"))
        self.assertEqual(facture.montant_tva, Decimal("200.00"))
        ligne.refresh_from_db()
        self.assertEqual(ligne.facture_id, facture.id)
        # Le statut du contrat n'a pas bougé.
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, "actif")

    def test_garde_facturation_non_activee(self):
        _, _, ligne = make_setup(self.co, facturation_active=False)
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)

    def test_garde_idempotence_deja_facturee(self):
        _, _, ligne = make_setup(self.co)
        services.facturer_ligne_echeance(ligne, user=self.user)
        ligne.refresh_from_db()
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)
        # Une seule facture créée.
        self.assertEqual(Facture.objects.filter(company=self.co).count(), 1)

    def test_garde_montant_nul(self):
        _, _, ligne = make_setup(self.co, montant="0")
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)

    def test_garde_sans_client(self):
        _, _, ligne = make_setup(self.co, client=False)
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)


class FacturationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("facrec-api", "FacRecApi")
        self.admin = make_user(self.co, "facrec-api-admin", role="admin")

    def test_action_facturer(self):
        _, _, ligne = make_setup(self.co, montant="2400")
        api = auth(self.admin)
        res = api.post(f"{LIGNES}{ligne.id}/facturer/", {}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertIsNotNone(res.data["facture_id"])
        self.assertTrue(res.data["facture_reference"])
        self.assertEqual(res.data["ligne"]["facture_id"], res.data["facture_id"])

    def test_action_facturer_non_activee_400(self):
        _, _, ligne = make_setup(self.co, facturation_active=False)
        api = auth(self.admin)
        res = api.post(f"{LIGNES}{ligne.id}/facturer/", {}, format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_role_gate(self):
        _, _, ligne = make_setup(self.co)
        commercial = make_user(self.co, "facrec-api-com", role="commercial")
        api = auth(commercial)
        res = api.post(f"{LIGNES}{ligne.id}/facturer/", {}, format="json")
        self.assertEqual(res.status_code, 403)
