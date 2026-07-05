"""ZSAV3 — Activités planifiées à échéance sur le ticket (rappeler / rappel
visite).

Couvre :
  * activité créée avec échéance ;
  * cochée = faite (idempotent) ;
  * échéance passée non faite → `en_retard` True, listée ;
  * cross-tenant 404 ;
  * assigné d'une autre société refusé.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zsav3 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket, TicketActiviteAFaire

User = get_user_model()


def make_company(slug='sav-zsav3', nom='Sav Co ZSAV3'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZSAV3ActiviteAFaireTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zsav3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.other_company = make_company(
            slug='sav-zsav3-other', nom='Sav Co ZSAV3 Other')
        self.other_admin = User.objects.create_user(
            username='zsav3_other_admin', password='x', role_legacy='admin',
            company=self.other_company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZSAV3',
            email='zsav3-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZSAV3', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ZSAV3-1',
            client=self.client_obj, installation=self.inst,
            created_by=self.admin)

    def test_creation_avec_echeance(self):
        r = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/activites/', {
                'type': 'appel', 'titre': 'Rappeler le client',
                'echeance': (date.today() + timedelta(days=3)).isoformat(),
            }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['fait'])
        act = TicketActiviteAFaire.objects.get(pk=r.data['id'])
        self.assertEqual(act.company_id, self.company.id)
        self.assertEqual(act.ticket_id, self.ticket.id)

    def test_cocher_idempotent(self):
        act = TicketActiviteAFaire.objects.create(
            company=self.company, ticket=self.ticket, type='appel',
            titre='Rappeler', echeance=date.today(),
            created_by=self.admin)
        r1 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}'
            f'/activites/{act.pk}/cocher/', {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertTrue(r1.data['fait'])
        fait_le_1 = r1.data['fait_le']

        r2 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}'
            f'/activites/{act.pk}/cocher/', {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['fait_le'], fait_le_1)  # inchangé.

    def test_echeance_passee_non_faite_en_retard(self):
        act = TicketActiviteAFaire.objects.create(
            company=self.company, ticket=self.ticket, type='rappel',
            titre='Suivi', echeance=date.today() - timedelta(days=5),
            created_by=self.admin)
        r = self.api.get(f'/api/django/sav/tickets/{self.ticket.pk}/activites/')
        self.assertEqual(r.status_code, 200, r.data)
        row = next(x for x in r.data if x['id'] == act.id)
        self.assertTrue(row['en_retard'])

    def test_echeance_future_pas_en_retard(self):
        act = TicketActiviteAFaire.objects.create(
            company=self.company, ticket=self.ticket, type='visite',
            titre='Visite planifiée',
            echeance=date.today() + timedelta(days=10),
            created_by=self.admin)
        r = self.api.get(f'/api/django/sav/tickets/{self.ticket.pk}/activites/')
        row = next(x for x in r.data if x['id'] == act.id)
        self.assertFalse(row['en_retard'])

    def test_cross_tenant_404(self):
        other_api = auth(self.other_admin)
        r = other_api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/activites/', {
                'type': 'appel', 'titre': 'x',
                'echeance': date.today().isoformat(),
            }, format='json')
        self.assertEqual(r.status_code, 404, r.data)

    def test_assigne_autre_societe_refuse(self):
        r = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/activites/', {
                'type': 'appel', 'titre': 'x',
                'echeance': date.today().isoformat(),
                'assigne': self.other_admin.id,
            }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
