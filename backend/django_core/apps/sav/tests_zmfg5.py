"""ZMFG5 — Onglet « Instructions » structuré sur le ticket.

Couvre :
  * champ `instructions` éditable et affiché ;
  * distinct de `description` et des notes chatter ;
  * migration additive (défaut '').

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg5 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket

User = get_user_model()


def make_company(slug='sav-zmfg5', nom='Sav Co ZMFG5'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG5InstructionsTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg5_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG5',
            email='zmfg5-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG5', client=self.client_obj)

    def _ticket(self, **kwargs):
        defaults = dict(
            company=self.company, client=self.client_obj,
            installation=self.inst, created_by=self.admin,
            reference='SAV-ZMFG5-1')
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def test_defaut_vide_migration_additive(self):
        t = self._ticket()
        self.assertEqual(t.instructions, '')

    def test_instructions_editable_et_affiche(self):
        t = self._ticket()
        r = self.api.patch(f'/api/django/sav/tickets/{t.id}/', {
            'instructions': 'Couper le disjoncteur avant intervention.',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            r.data['instructions'],
            'Couper le disjoncteur avant intervention.')
        t.refresh_from_db()
        self.assertEqual(
            t.instructions, 'Couper le disjoncteur avant intervention.')

    def test_distinct_de_description_et_chatter(self):
        t = self._ticket(description='Onduleur en panne')
        self.api.patch(f'/api/django/sav/tickets/{t.id}/', {
            'instructions': 'Vérifier le fusible AC.',
        }, format='json')
        t.refresh_from_db()
        self.assertEqual(t.description, 'Onduleur en panne')
        self.assertEqual(t.instructions, 'Vérifier le fusible AC.')
