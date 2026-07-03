"""Tests XCTR13 — Unification sav.ContratMaintenance <-> apps/contrats.

Couvre :
- validation à l'écriture de sav_contrat_maintenance_id (id invalide/autre
  société refusé, valide/vide accepté) ;
- MRR combiné exact sans doublon (contrat lié compté une fois côté contrat).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.sav.models import ContratMaintenance

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


def make_contrat_maintenance(company, *, prix=Decimal("600"),
                             periodicite="mensuel", facturation_active=True,
                             actif=True):
    cli = Client.objects.create(company=company, nom="Client CM")
    return ContratMaintenance.objects.create(
        company=company, client=cli, periodicite=periodicite,
        date_debut=date(2026, 1, 1), prix=prix, actif=actif,
        facturation_active=facturation_active)


def make_contrat(company, *, montant=Decimal("1000"),
                 sav_contrat_maintenance_id=None):
    cli = Client.objects.create(company=company, nom="Client Contrat")
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=montant,
        type_contrat="om", statut=Contrat.Statut.ACTIF,
        client_id=cli.id, date_debut=date(2026, 1, 1),
        sav_contrat_maintenance_id=sav_contrat_maintenance_id)
    EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF,
        montant_total=montant)
    return contrat


class ValidationSavContratMaintenanceIdTests(TestCase):
    def setUp(self):
        self.co = make_company("unif-valid", "UnifValid")
        self.admin = make_user(self.co, "unif-valid-admin")

    def test_id_valide_accepte(self):
        cm = make_contrat_maintenance(self.co)
        cli = Client.objects.create(company=self.co, nom="Client")
        api = auth(self.admin)
        res = api.post(CONTRATS, {
            'objet': 'Contrat lié', 'type_contrat': 'om',
            'client_id': cli.id, 'sav_contrat_maintenance_id': cm.id,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data['sav_contrat_maintenance_id'], cm.id)

    def test_id_inexistant_refuse(self):
        cli = Client.objects.create(company=self.co, nom="Client")
        api = auth(self.admin)
        res = api.post(CONTRATS, {
            'objet': 'Contrat invalide', 'type_contrat': 'om',
            'client_id': cli.id, 'sav_contrat_maintenance_id': 999999,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_id_autre_societe_refuse(self):
        autre = make_company("unif-valid-autre", "UnifValidAutre")
        cm_etranger = make_contrat_maintenance(autre)
        cli = Client.objects.create(company=self.co, nom="Client")
        api = auth(self.admin)
        res = api.post(CONTRATS, {
            'objet': 'Contrat cross-tenant', 'type_contrat': 'om',
            'client_id': cli.id,
            'sav_contrat_maintenance_id': cm_etranger.id,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_sans_id_accepte(self):
        cli = Client.objects.create(company=self.co, nom="Client")
        api = auth(self.admin)
        res = api.post(CONTRATS, {
            'objet': 'Contrat sans lien', 'type_contrat': 'om',
            'client_id': cli.id,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.content)


class MrrCombineTests(TestCase):
    def setUp(self):
        self.co = make_company("unif-mrr", "UnifMrr")

    def test_combine_sans_lien_additionne(self):
        make_contrat(self.co, montant=Decimal("1000"))
        make_contrat_maintenance(self.co, prix=Decimal("600"))
        total = selectors.mrr_combine(self.co)
        self.assertEqual(total, Decimal('1600.00'))

    def test_combine_avec_lien_sans_doublon(self):
        cm = make_contrat_maintenance(self.co, prix=Decimal("600"))
        # Contrat lié : le MRR de la maintenance NE doit PAS être compté deux
        # fois — seul l'échéancier du contrat (1000) compte, la part
        # maintenance SAV (600) est exclue.
        make_contrat(
            self.co, montant=Decimal("1000"),
            sav_contrat_maintenance_id=cm.id)
        total = selectors.mrr_combine(self.co)
        self.assertEqual(total, Decimal('1000.00'))

    def test_mrr_maintenance_sav_exclut_non_facturable(self):
        make_contrat_maintenance(
            self.co, prix=Decimal("600"), facturation_active=False)
        total = selectors.mrr_maintenance_sav(self.co)
        self.assertEqual(total, Decimal('0.00'))

    def test_scope_societe(self):
        autre = make_company("unif-mrr-autre", "UnifMrrAutre")
        make_contrat_maintenance(autre, prix=Decimal("999"))
        make_contrat_maintenance(self.co, prix=Decimal("600"))
        total = selectors.mrr_maintenance_sav(self.co)
        self.assertEqual(total, Decimal('600.00'))
