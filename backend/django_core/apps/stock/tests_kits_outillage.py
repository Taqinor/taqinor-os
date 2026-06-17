"""F2 — Kits d'outillage tests.

Run:
    docker compose exec django_core python manage.py test apps.stock.tests_kits_outillage -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Outillage, KitOutillage, KitOutillageItem
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/stock/kits-outillage/'


def rows(resp):
    """Lignes d'une réponse liste (paginée ou non)."""
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class KitBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='kit-co', defaults={'nom': 'Kit Co'})[0]
        self.other = Company.objects.get_or_create(
            slug='kit-co-2', defaults={'nom': 'Other Co'})[0]
        self.admin = User.objects.create_user(
            username='kit_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def tool(self, company=None, nom='Perceuse'):
        return Outillage.objects.create(company=company or self.company, nom=nom)


class TestKitSeeding(KitBase):
    def test_list_seeds_three_default_kits(self):
        resp = self.api.get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        noms = [k['nom'] for k in rows(resp)]
        self.assertIn('Kit pose structure', noms)
        self.assertIn('Kit raccordement électrique', noms)
        self.assertIn('Kit mise en service', noms)
        # seeded kits are protected (deactivate-not-delete) and empty
        kit = KitOutillage.objects.get(company=self.company, nom='Kit pose structure')
        self.assertTrue(kit.protege)
        self.assertEqual(kit.items.count(), 0)

    def test_seeding_is_idempotent(self):
        self.api.get(BASE)
        self.api.get(BASE)
        self.assertEqual(
            KitOutillage.objects.filter(company=self.company).count(), 3)


class TestKitCrud(KitBase):
    def test_create_kit_with_ordered_tools(self):
        t1, t2 = self.tool(nom='A'), self.tool(nom='B')
        resp = self.api.post(BASE, {
            'nom': 'Kit perso', 'type_intervention': 'pose',
            'items': [{'outil': t2.id, 'ordre': 0}, {'outil': t1.id, 'ordre': 1}],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        kit = KitOutillage.objects.get(nom='Kit perso')
        self.assertEqual(kit.company, self.company)  # forced server-side
        self.assertEqual(
            list(kit.items.order_by('ordre').values_list('outil__nom', flat=True)),
            ['B', 'A'])

    def test_update_replaces_items(self):
        t1, t2 = self.tool(nom='A'), self.tool(nom='B')
        kit = KitOutillage.objects.create(company=self.company, nom='K')
        KitOutillageItem.objects.create(kit=kit, outil=t1, ordre=0)
        resp = self.api.patch(f'{BASE}{kit.id}/', {
            'items': [{'outil': t2.id, 'ordre': 0}]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            list(kit.items.values_list('outil__nom', flat=True)), ['B'])

    def test_cannot_add_other_company_tool(self):
        foreign = self.tool(company=self.other, nom='Pas à moi')
        resp = self.api.post(BASE, {
            'nom': 'Kit X', 'items': [{'outil': foreign.id, 'ordre': 0}],
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_deactivate_keeps_kit(self):
        kit = KitOutillage.objects.create(company=self.company, nom='K', actif=True)
        resp = self.api.patch(f'{BASE}{kit.id}/', {'actif': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        kit.refresh_from_db()
        self.assertFalse(kit.actif)

    def test_protected_kit_cannot_be_deleted(self):
        self.api.get(BASE)  # seed
        kit = KitOutillage.objects.get(company=self.company, nom='Kit mise en service')
        resp = self.api.delete(f'{BASE}{kit.id}/')
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(KitOutillage.objects.filter(id=kit.id).exists())

    def test_list_is_company_scoped(self):
        KitOutillage.objects.create(company=self.other, nom='Étranger')
        resp = self.api.get(BASE)
        self.assertNotIn('Étranger', [k['nom'] for k in rows(resp)])
