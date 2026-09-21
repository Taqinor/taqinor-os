"""Tests de la conversion tâche de projet → ticket SAV (ZPRJ11).

Couvre : conversion crée le ticket dans la MÊME société, réutilise
``apps.sav.services.create_ticket_from_projet_tache`` (jamais un import de
``sav.models`` depuis ``gestion_projet`` — vérifié statiquement par
import-linter, ici on vérifie le comportement), une tâche d'une autre
société → 404, une re-conversion → 400, tâche sans client résolvable → 400,
migration additive (``ticket_sav_id``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.gestion_projet import services
from apps.gestion_projet.models import Projet, Tache
from apps.sav.models import Ticket

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ConvertirTacheEnTicketSavServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z11-svc', 'S')
        self.client_crm = Client.objects.create(company=self.co, nom='Client')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z11', nom='P', client_id=self.client_crm.id)
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Fuite toiture',
            description='Une fuite constatée', ordre=1)
        self.user = make_user(self.co, 'z11-svc-u')

    def test_conversion_cree_ticket_meme_societe(self):
        ticket = services.convertir_tache_en_ticket_sav(
            self.tache, user=self.user)
        self.assertIsInstance(ticket, Ticket)
        self.assertEqual(ticket.company_id, self.co.id)
        self.assertEqual(ticket.client_id, self.client_crm.id)
        self.assertEqual(ticket.type, Ticket.Type.CORRECTIF)
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.ticket_sav_id, ticket.id)

    def test_reconversion_refusee(self):
        services.convertir_tache_en_ticket_sav(self.tache, user=self.user)
        with self.assertRaises(services.ConversionTicketSavError):
            services.convertir_tache_en_ticket_sav(self.tache, user=self.user)

    def test_sans_client_resolvable_refuse(self):
        projet_sans_client = Projet.objects.create(
            company=self.co, code='P-Z11-NC', nom='Sans client')
        tache = Tache.objects.create(
            company=self.co, projet=projet_sans_client, libelle='T', ordre=1)
        with self.assertRaises(services.ConversionTicketSavError):
            services.convertir_tache_en_ticket_sav(tache, user=self.user)


class ConvertirTacheEnTicketSavApiTests(TestCase):
    BASE = '/api/django/gestion-projet/taches/'

    def setUp(self):
        self.co_a = make_company('gp-z11-a', 'A')
        self.co_b = make_company('gp-z11-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-z11-a-u')
        self.user_b = make_user(self.co_b, 'gp-z11-b-u')
        self.client_crm = Client.objects.create(company=self.co_a, nom='Client A')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-Z11A', nom='A',
            client_id=self.client_crm.id)
        self.tache_a = Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='T-A', ordre=1)

    def test_endpoint_convertit(self):
        api = auth(self.user_a)
        resp = api.post(f'{self.BASE}{self.tache_a.id}/vers-ticket-sav/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('ticket_sav_id', resp.data)

    def test_endpoint_reconversion_400(self):
        api = auth(self.user_a)
        api.post(f'{self.BASE}{self.tache_a.id}/vers-ticket-sav/')
        resp = api.post(f'{self.BASE}{self.tache_a.id}/vers-ticket-sav/')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe_404(self):
        api = auth(self.user_b)
        resp = api.post(f'{self.BASE}{self.tache_a.id}/vers-ticket-sav/')
        self.assertEqual(resp.status_code, 404)
