"""XQHS23 — Pont SAV ↔ NCR (boucle défaillances terrain/garantie).

Couvre :
  * ticket SAV → NCR fonctionne, idempotent, company-scoped, aucun import de
    modèle cross-app ;
  * NCR → intervention SAV fonctionne, idempotent ;
  * le taux de défaillance par produit s'affiche au cockpit ;
  * scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models_installation import Installation
from apps.qhse.models import NonConformite
from apps.qhse.selectors import taux_defaillance_par_produit
from apps.qhse.services import (
    creer_intervention_depuis_ncr, creer_ncr_depuis_ticket,
)
from apps.sav.models import Equipement, Ticket
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company, client):
    return Installation.objects.create(company=company, client=client)


def make_ticket(company, installation, client, **kwargs):
    defaults = dict(
        company=company, reference='SAV-TEST-1', client=client,
        installation=installation, description='Panne onduleur')
    defaults.update(kwargs)
    return Ticket.objects.create(**defaults)


class CreerNcrDepuisTicketTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs23-t2n', 'Xqhs23 T2N')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client A')
        self.installation = make_installation(self.company, self.client_obj)
        self.ticket = make_ticket(
            self.company, self.installation, self.client_obj)

    def test_cree_ncr_depuis_ticket(self):
        ncr, created = creer_ncr_depuis_ticket(self.ticket.pk, self.company)
        self.assertTrue(created)
        self.assertIsInstance(ncr, NonConformite)
        self.assertEqual(ncr.ticket_sav_id, self.ticket.pk)
        self.assertEqual(ncr.chantier_id, self.installation.pk)

    def test_idempotent(self):
        ncr1, created1 = creer_ncr_depuis_ticket(self.ticket.pk, self.company)
        ncr2, created2 = creer_ncr_depuis_ticket(self.ticket.pk, self.company)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(ncr1.pk, ncr2.pk)

    def test_ticket_hors_societe_leve_valueerror(self):
        other_co = make_company('xqhs23-t2n-other', 'Xqhs23 T2N Other')
        with self.assertRaises(ValueError):
            creer_ncr_depuis_ticket(self.ticket.pk, other_co)

    def test_ticket_inconnu_leve_valueerror(self):
        with self.assertRaises(ValueError):
            creer_ncr_depuis_ticket(999999, self.company)


class CreerInterventionDepuisNcrTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs23-n2t', 'Xqhs23 N2T')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client B')
        self.installation = make_installation(self.company, self.client_obj)

    def test_cree_intervention_depuis_ncr(self):
        ncr = NonConformite.objects.create(
            company=self.company, titre='Défaut structure',
            chantier_id=self.installation.pk, reference='NCR-001')
        ticket, created = creer_intervention_depuis_ncr(ncr)
        self.assertTrue(created)
        self.assertIsInstance(ticket, Ticket)
        self.assertEqual(ticket.installation_id, self.installation.pk)
        self.assertEqual(ticket.client_id, self.client_obj.pk)

    def test_idempotent(self):
        ncr = NonConformite.objects.create(
            company=self.company, titre='Défaut structure',
            chantier_id=self.installation.pk, reference='NCR-002')
        ticket1, created1 = creer_intervention_depuis_ncr(ncr)
        ticket2, created2 = creer_intervention_depuis_ncr(ncr)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(ticket1.pk, ticket2.pk)

    def test_ncr_sans_chantier_leve_valueerror(self):
        ncr = NonConformite.objects.create(
            company=self.company, titre='NCR sans chantier')
        with self.assertRaises(ValueError):
            creer_intervention_depuis_ncr(ncr)


class TauxDefaillanceParProduitTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs23-taux', 'Xqhs23 Taux')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client C')
        self.installation = make_installation(self.company, self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur XYZ', prix_vente=0)
        self.equipement = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.installation, numero_serie='SN-001')

    def test_groupe_par_produit(self):
        ticket1 = make_ticket(
            self.company, self.installation, self.client_obj,
            reference='SAV-1', equipement=self.equipement)
        ticket2 = make_ticket(
            self.company, self.installation, self.client_obj,
            reference='SAV-2', equipement=self.equipement)
        creer_ncr_depuis_ticket(ticket1.pk, self.company)
        creer_ncr_depuis_ticket(ticket2.pk, self.company)

        taux = taux_defaillance_par_produit(self.company)
        self.assertEqual(len(taux), 1)
        self.assertEqual(taux[0]['produit_id'], self.produit.pk)
        self.assertEqual(taux[0]['nb_ncr'], 2)

    def test_sans_ncr_sav_liste_vide(self):
        taux = taux_defaillance_par_produit(self.company)
        self.assertEqual(taux, [])

    def test_scope_societe(self):
        other_co = make_company('xqhs23-taux-other', 'Xqhs23 Taux Other')
        other_client = Client.objects.create(company=other_co, nom='Autre')
        other_installation = make_installation(other_co, other_client)
        other_ticket = make_ticket(
            other_co, other_installation, other_client, reference='SAV-X')
        creer_ncr_depuis_ticket(other_ticket.pk, other_co)
        taux = taux_defaillance_par_produit(self.company)
        self.assertEqual(taux, [])


class PontApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs23-api', 'Xqhs23 Api')
        self.user = make_user(self.company, 'xqhs23-user')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client D')
        self.installation = make_installation(self.company, self.client_obj)

    def test_depuis_ticket_sav_action(self):
        ticket = make_ticket(self.company, self.installation, self.client_obj)
        resp = auth(self.user).post(
            '/api/django/qhse/non-conformites/depuis-ticket-sav/',
            {'ticket': ticket.pk}, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_creer_intervention_action(self):
        ncr = NonConformite.objects.create(
            company=self.company, titre='Défaut',
            chantier_id=self.installation.pk, reference='NCR-API-1')
        resp = auth(self.user).post(
            f'/api/django/qhse/non-conformites/{ncr.pk}/creer-intervention/')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('ticket_id', resp.data)

    def test_taux_defaillance_produit_endpoint(self):
        resp = auth(self.user).get(
            '/api/django/qhse/non-conformites/taux-defaillance-produit/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])
