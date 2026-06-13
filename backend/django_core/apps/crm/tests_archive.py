"""
Tests archivage / suppression des leads (WS2, 2026-06-13).

Archivage réversible (Commerciale) : cache des vues par défaut, filtre
« Archivés », restauration. Suppression définitive : admin uniquement,
bloquée si des devis sont liés. Aucune donnée de production touchée — TestCase
utilise une base jetable annulée à la fin.

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_archive -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead, Client, LeadActivity
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug='arch-co', nom='Arch Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    """IDs d'une liste DRF, paginée (dict {results}) ou non (liste brute)."""
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [x['id'] for x in rows]


class ArchiveTestBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.resp = User.objects.create_user(
            username='arch_resp', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.admin = User.objects.create_user(
            username='arch_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.lead = Lead.objects.create(
            company=self.company, nom='Test', prenom='Lead', stage='NEW',
        )


class TestArchiveRestore(ArchiveTestBase):
    def test_archive_hides_from_default_list_and_filters_bring_it_back(self):
        api = auth(self.resp)
        # Visible par défaut
        r = api.get('/api/django/crm/leads/')
        ids = ids_of(r)
        self.assertIn(self.lead.id, ids)
        # Archive
        a = api.post(f'/api/django/crm/leads/{self.lead.id}/archiver/')
        self.assertEqual(a.status_code, 200, a.data)
        self.assertTrue(a.data['is_archived'])
        # Disparaît de la liste par défaut
        r = api.get('/api/django/crm/leads/')
        ids = ids_of(r)
        self.assertNotIn(self.lead.id, ids)
        # Réapparaît avec ?archived=only
        r = api.get('/api/django/crm/leads/?archived=only')
        ids = ids_of(r)
        self.assertIn(self.lead.id, ids)
        # Et avec ?archived=all
        r = api.get('/api/django/crm/leads/?archived=all')
        ids = ids_of(r)
        self.assertIn(self.lead.id, ids)

    def test_restore_returns_lead_to_default_views(self):
        api = auth(self.resp)
        api.post(f'/api/django/crm/leads/{self.lead.id}/archiver/')
        rest = api.post(f'/api/django/crm/leads/{self.lead.id}/restaurer/')
        self.assertEqual(rest.status_code, 200, rest.data)
        self.assertFalse(rest.data['is_archived'])
        r = api.get('/api/django/crm/leads/')
        ids = ids_of(r)
        self.assertIn(self.lead.id, ids)

    def test_archive_is_logged_in_chatter(self):
        api = auth(self.resp)
        api.post(f'/api/django/crm/leads/{self.lead.id}/archiver/')
        bodies = [a.body for a in LeadActivity.objects.filter(lead=self.lead)]
        self.assertTrue(any('archivé' in (b or '').lower() for b in bodies))

    def test_archive_records_who(self):
        api = auth(self.resp)
        api.post(f'/api/django/crm/leads/{self.lead.id}/archiver/')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.archived_by_id, self.resp.id)
        self.assertIsNotNone(self.lead.archived_at)


class TestHardDelete(ArchiveTestBase):
    def test_commerciale_cannot_hard_delete(self):
        api = auth(self.resp)
        r = api.delete(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Lead.objects.filter(pk=self.lead.id).exists())

    def test_admin_can_hard_delete_lead_without_devis(self):
        api = auth(self.admin)
        r = api.delete(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Lead.objects.filter(pk=self.lead.id).exists())

    def test_delete_blocked_when_lead_has_devis(self):
        client = Client.objects.create(
            company=self.company, nom='Client', email='c@example.com',
        )
        Devis.objects.create(
            company=self.company, reference='DEV-TEST-0001', client=client,
            lead=self.lead, statut='brouillon', taux_tva=Decimal('20.00'),
        )
        api = auth(self.admin)
        r = api.delete(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 409)
        self.assertTrue(Lead.objects.filter(pk=self.lead.id).exists())
