"""NTDMO28 — masquage PAR SOCIÉTÉ d'un item du catalogue « Premiers pas »
(table de jonction additive `masque_pour`, jamais une suppression). Paramètre
par tenant : une société masque un item non pertinent pour son activité, un
item masqué par une société reste visible pour toutes les autres.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.onboarding.models import OnboardingChecklistItem
from apps.onboarding.selectors import (
    checklist_pour_utilisateur, items_masquables_pour_societe,
)
from apps.onboarding.services import (
    demasquer_item_pour_societe, marquer_item_complete,
    masquer_item_pour_societe,
)
from apps.roles.models import Role

User = get_user_model()


class MasquageServiceTest(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(nom='A', slug='co-mask-a')
        self.company_b = Company.objects.create(nom='B', slug='co-mask-b')
        self.role_a = Role.objects.create(company=self.company_a, nom='Administrateur')
        self.role_b = Role.objects.create(company=self.company_b, nom='Administrateur')
        self.user_a = User.objects.create_user(
            'u-mask-a', password='x', company=self.company_a, role=self.role_a)
        self.user_b = User.objects.create_user(
            'u-mask-b', password='x', company=self.company_b, role=self.role_b)

    def test_masking_hides_item_only_for_that_company(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        masquer_item_pour_societe(self.company_a, item.id)
        keys_a = {it['key'] for it in checklist_pour_utilisateur(self.company_a, self.user_a)}
        keys_b = {it['key'] for it in checklist_pour_utilisateur(self.company_b, self.user_b)}
        self.assertNotIn('import_clients', keys_a)
        self.assertIn('import_clients', keys_b)

    def test_masking_never_deletes_the_catalogue_item(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        masquer_item_pour_societe(self.company_a, item.id)
        self.assertTrue(
            OnboardingChecklistItem.objects.filter(pk=item.id).exists())

    def test_masking_is_idempotent(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        masquer_item_pour_societe(self.company_a, item.id)
        masquer_item_pour_societe(self.company_a, item.id)
        self.assertEqual(item.masque_pour.filter(pk=self.company_a.pk).count(), 1)

    def test_demasquer_shows_it_again(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        masquer_item_pour_societe(self.company_a, item.id)
        demasquer_item_pour_societe(self.company_a, item.id)
        keys_a = {it['key'] for it in checklist_pour_utilisateur(self.company_a, self.user_a)}
        self.assertIn('import_clients', keys_a)

    def test_items_masquables_reflects_status_per_company(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        masquer_item_pour_societe(self.company_a, item.id)
        rows_a = {r['key']: r['masque'] for r in items_masquables_pour_societe(self.company_a)}
        rows_b = {r['key']: r['masque'] for r in items_masquables_pour_societe(self.company_b)}
        self.assertTrue(rows_a['import_clients'])
        self.assertFalse(rows_b['import_clients'])

    def test_masking_a_done_item_still_hides_it_from_the_list(self):
        # Un item déjà FAIT reste caché quand la société le masque ensuite —
        # comportement cohérent avec `ignorer_item` (l'item n'apparaît plus).
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        marquer_item_complete(self.company_a, self.user_a, 'import_clients')
        masquer_item_pour_societe(self.company_a, item.id)
        keys_a = {it['key'] for it in checklist_pour_utilisateur(self.company_a, self.user_a)}
        self.assertNotIn('import_clients', keys_a)


class MasquageEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ep28', slug='co-ep28')
        self.role_admin = Role.objects.create(company=self.company, nom='Administrateur')
        self.role_limite = Role.objects.create(company=self.company, nom='Commercial')
        self.admin = User.objects.create_user(
            'admin-28', password='x', company=self.company, role=self.role_admin)
        self.limite = User.objects.create_user(
            'lim-28', password='x', company=self.company, role=self.role_limite)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_list_requires_admin_or_responsable_tier(self):
        r = self._client(self.limite).get('/api/django/onboarding/items-masques/')
        self.assertEqual(r.status_code, 403)

    def test_list_returns_global_catalogue_with_masque_flag(self):
        r = self._client(self.admin).get('/api/django/onboarding/items-masques/')
        self.assertEqual(r.status_code, 200)
        keys = {row['key'] for row in r.data}
        self.assertIn('import_clients', keys)
        self.assertTrue(all(row['masque'] is False for row in r.data))

    def test_masquer_then_demasquer_round_trip(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        c = self._client(self.admin)
        r1 = c.post(f'/api/django/onboarding/items-masques/{item.id}/masquer/')
        self.assertEqual(r1.status_code, 200)
        row = next(r for r in r1.data if r['key'] == 'import_clients')
        self.assertTrue(row['masque'])

        r2 = c.post(f'/api/django/onboarding/items-masques/{item.id}/demasquer/')
        self.assertEqual(r2.status_code, 200)
        row2 = next(r for r in r2.data if r['key'] == 'import_clients')
        self.assertFalse(row2['masque'])

    def test_masquer_requires_admin_or_responsable_tier(self):
        item = OnboardingChecklistItem.objects.get(key='import_clients')
        r = self._client(self.limite).post(
            f'/api/django/onboarding/items-masques/{item.id}/masquer/')
        self.assertEqual(r.status_code, 403)
