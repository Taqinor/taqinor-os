"""Tests XCTR9 — CLV côté contrats (selectors.clv_client + endpoint).

Couvre :
- ``mrr_client`` agrège le MRR des contrats actifs d'un client ;
- ``clv_client`` délègue à ``core.clv`` (churn/ARPC alimentés depuis contrats) ;
- endpoint ``/contrats/contrats/clv/?client_id=``.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client

from apps.contrats import selectors, services
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()

CLV = "/api/django/contrats/contrats/clv/"


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


def make_contrat(company, client_id, montant, *, actif=True):
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=montant,
        type_contrat="om",
        statut=Contrat.Statut.ACTIF if actif else Contrat.Statut.RESILIE,
        client_id=client_id, date_debut=date(2026, 1, 1))
    EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF,
        montant_total=montant)
    return contrat


class MrrClientTests(TestCase):
    def setUp(self):
        self.co = make_company("clv-mrr", "ClvMrr")

    def test_agrege_contrats_actifs_seulement(self):
        cli = Client.objects.create(company=self.co, nom="Client A")
        make_contrat(self.co, cli.id, Decimal("1000"))
        make_contrat(self.co, cli.id, Decimal("500"), actif=False)
        mrr = selectors.mrr_client(self.co, cli.id)
        self.assertEqual(mrr, Decimal('1000.00'))

    def test_client_sans_contrat_mrr_zero(self):
        self.assertEqual(selectors.mrr_client(self.co, 99999), Decimal('0.00'))


class ClvClientTests(TestCase):
    def setUp(self):
        self.co = make_company("clv-client", "ClvClient")

    def test_clv_sans_churn_calculable_est_none(self):
        cli = Client.objects.create(company=self.co, nom="Client A")
        make_contrat(self.co, cli.id, Decimal("1000"))
        resultat = selectors.clv_client(self.co, cli.id)
        # Aucune résiliation récente -> churn non calculable -> repli propre.
        self.assertIsNone(resultat.clv)
        self.assertTrue(resultat.used_fallback)

    def test_clv_avec_churn_observe(self):
        cli_perdu = Client.objects.create(company=self.co, nom="Client perdu")
        cli_cible = Client.objects.create(company=self.co, nom="Client cible")
        contrat_perdu = make_contrat(self.co, cli_perdu.id, Decimal("800"))
        make_contrat(self.co, cli_cible.id, Decimal("1000"))
        services.resilier_contrat(
            contrat_perdu, motif="Test churn", date_effet=date.today(),
            today=date.today())

        resultat = selectors.clv_client(self.co, cli_cible.id)
        self.assertIsNotNone(resultat.clv)
        self.assertFalse(resultat.used_fallback)


class ClvApiTests(TestCase):
    def setUp(self):
        self.co = make_company("clv-api", "ClvApi")
        self.admin = make_user(self.co, "clv-api-admin")

    def test_endpoint_retourne_clv(self):
        cli_perdu = Client.objects.create(company=self.co, nom="Client perdu")
        cli_cible = Client.objects.create(company=self.co, nom="Client cible")
        contrat_perdu = make_contrat(self.co, cli_perdu.id, Decimal("800"))
        make_contrat(self.co, cli_cible.id, Decimal("1000"))
        services.resilier_contrat(
            contrat_perdu, motif="Test", date_effet=date.today(),
            today=date.today())

        api = auth(self.admin)
        res = api.get(f"{CLV}?client_id={cli_cible.id}")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['client_id'], cli_cible.id)
        self.assertIsNotNone(res.data['clv'])

    def test_endpoint_400_sans_client_id(self):
        api = auth(self.admin)
        res = api.get(CLV)
        self.assertEqual(res.status_code, 400)

    def test_role_gate(self):
        commercial = make_user(self.co, "clv-api-com", role="commercial")
        api = auth(commercial)
        res = api.get(f"{CLV}?client_id=1")
        self.assertEqual(res.status_code, 403)
