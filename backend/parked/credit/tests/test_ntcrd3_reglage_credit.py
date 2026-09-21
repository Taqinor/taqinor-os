"""NTCRD3 — ``ReglageCredit`` (1-1 société) : défauts NON bloquants
(aucun hold tant que le founder n'active rien)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.credit.models import LimiteCredit, ReglageCredit

User = get_user_model()


def make_company(slug='ntcrd3-co', nom='NTCRD3 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD3ReglageCreditTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd3_admin', password='x', role_legacy='admin',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='ntcrd3_com', password='x', role_legacy='normal',
            company=self.company)

    def test_defaults_reproduce_no_hold_behaviour(self):
        """Aucun ReglageCredit créé => defaults = avertissement (jamais blocage)."""
        reglage = ReglageCredit.get_or_default(self.company)
        self.assertEqual(reglage.mode_hold_defaut, LimiteCredit.ModeHold.AVERTISSEMENT)
        self.assertIsNone(reglage.pk)

    def test_get_endpoint_returns_defaults(self):
        r = auth(self.admin).get('/api/django/credit/reglage/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['mode_hold_defaut'], 'avertissement')
        self.assertEqual(Decimal(r.data['seuil_alerte_pct']), Decimal('80.00'))

    def test_patch_requires_responsable_or_admin(self):
        r = auth(self.commercial).patch(
            '/api/django/credit/reglage/', {'mode_hold_defaut': 'blocage'},
            format='json')
        self.assertEqual(r.status_code, 403)

    def test_admin_can_patch_and_it_persists(self):
        r = auth(self.admin).patch(
            '/api/django/credit/reglage/', {'mode_hold_defaut': 'blocage'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        reglage = ReglageCredit.objects.get(company=self.company)
        self.assertEqual(reglage.mode_hold_defaut, 'blocage')
