"""Tests XCTR10 — Responsable (owner) sur le contrat + MRR par commercial.

Couvre :
- CRUD + filtre ``?responsable=`` OK ;
- agrégats par responsable exacts (tableau de bord + mouvements XCTR7) ;
- un utilisateur d'une autre société est refusé (validation same-company) ;
- migration additive (comportement inchangé sans responsable).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client

from apps.contrats import selectors
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"


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


def make_contrat(company, *, responsable=None, montant=Decimal("1000")):
    cli = Client.objects.create(company=company, nom="Client SARL")
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=montant,
        type_contrat="om", statut=Contrat.Statut.ACTIF,
        client_id=cli.id, responsable=responsable,
        date_debut=date(2026, 1, 1))
    EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF,
        montant_total=montant)
    return contrat


class ResponsableModelTests(TestCase):
    def setUp(self):
        self.co = make_company("resp-model", "RespModel")
        self.commercial = make_user(self.co, "resp-model-com", role="commercial")

    def test_contrat_sans_responsable_comportement_inchange(self):
        contrat = make_contrat(self.co)
        self.assertIsNone(contrat.responsable_id)

    def test_contrat_avec_responsable(self):
        contrat = make_contrat(self.co, responsable=self.commercial)
        self.assertEqual(contrat.responsable_id, self.commercial.id)


class ResponsableApiTests(TestCase):
    def setUp(self):
        self.co = make_company("resp-api", "RespApi")
        self.admin = make_user(self.co, "resp-api-admin")
        self.commercial = make_user(self.co, "resp-api-com", role="commercial")

    def test_filtre_par_responsable(self):
        make_contrat(self.co, responsable=self.commercial)
        make_contrat(self.co)
        api = auth(self.admin)
        res = api.get(f"{CONTRATS}?responsable={self.commercial.id}")
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        self.assertEqual(len(results), 1)

    def test_creation_avec_responsable_meme_societe(self):
        cli = Client.objects.create(company=self.co, nom="Client B")
        api = auth(self.admin)
        res = api.post(CONTRATS, {
            'objet': 'Nouveau contrat', 'type_contrat': 'om',
            'client_id': cli.id, 'responsable': self.commercial.id,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data['responsable'], self.commercial.id)

    def test_responsable_autre_societe_refuse(self):
        autre_co = make_company("resp-api-autre", "RespApiAutre")
        etranger = make_user(autre_co, "resp-api-etranger")
        cli = Client.objects.create(company=self.co, nom="Client C")
        api = auth(self.admin)
        res = api.post(CONTRATS, {
            'objet': 'Contrat refuse', 'type_contrat': 'om',
            'client_id': cli.id, 'responsable': etranger.id,
        }, format='json')
        self.assertEqual(res.status_code, 400)


class MrrParResponsableTests(TestCase):
    def setUp(self):
        self.co = make_company("resp-mrr", "RespMrr")
        self.com1 = make_user(self.co, "resp-mrr-com1", role="commercial")
        self.com2 = make_user(self.co, "resp-mrr-com2", role="commercial")

    def test_ventilation_dashboard_exacte(self):
        make_contrat(self.co, responsable=self.com1, montant=Decimal("1000"))
        make_contrat(self.co, responsable=self.com1, montant=Decimal("500"))
        make_contrat(self.co, responsable=self.com2, montant=Decimal("300"))
        make_contrat(self.co, montant=Decimal("200"))  # sans responsable

        data = selectors.tableau_de_bord_contrats(self.co)
        ventilation = data['mrr_par_responsable']
        self.assertEqual(ventilation[self.com1.id], Decimal('1500.00'))
        self.assertEqual(ventilation[self.com2.id], Decimal('300.00'))
        self.assertEqual(ventilation['sans_responsable'], Decimal('200.00'))

    def test_ventilation_mouvements_new(self):
        contrat = make_contrat(
            self.co, responsable=self.com1, montant=Decimal("1000"))
        today = contrat.date_creation.date()
        data = selectors.mouvements_mrr(self.co, today, today)
        self.assertEqual(
            data['net_par_responsable'][self.com1.id], Decimal('1000.00'))
