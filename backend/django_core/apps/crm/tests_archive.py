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


class TestSoftDelete(ArchiveTestBase):
    """VX96 — la suppression d'un lead est désormais un SOFT-DELETE réversible.

    ``Lead`` est le premier adoptant de ``core.SoftDeleteModel`` (FG388) :
    ``destroy()`` appelle ``soft_delete`` (le lead sort des querysets par
    défaut, une entrée de corbeille ``DeletionRecord`` est créée, restaurable
    30 min via ``/core/corbeille/``). Aucune destruction physique.
    """

    def test_commerciale_cannot_delete(self):
        api = auth(self.resp)
        r = api.delete(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 403)
        # Ni soft ni hard : le lead reste vivant.
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.is_deleted)

    def test_admin_soft_deletes_lead_and_it_leaves_default_querysets(self):
        api = auth(self.admin)
        r = api.delete(f'/api/django/crm/leads/{self.lead.id}/')
        # Réponse 200 avec l'id de corbeille pour l'undo (plus de 204).
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('corbeille_id', r.data)
        self.assertIsNotNone(r.data['corbeille_id'])
        # La ligne existe TOUJOURS en base (soft-delete), mais est masquée du
        # manager par défaut et présente via all_objects.
        self.assertFalse(Lead.objects.filter(pk=self.lead.id).exists())
        self.assertTrue(Lead.all_objects.filter(pk=self.lead.id).exists())
        deleted = Lead.all_objects.get(pk=self.lead.id)
        self.assertTrue(deleted.is_deleted)
        self.assertEqual(deleted.deleted_by_id, self.admin.id)
        self.assertIsNotNone(deleted.deleted_at)
        # Disparaît de la liste API par défaut.
        r = api.get('/api/django/crm/leads/')
        self.assertNotIn(self.lead.id, ids_of(r))

    def test_soft_deleted_lead_is_restorable_within_undo_window(self):
        api = auth(self.admin)
        r = api.delete(f'/api/django/crm/leads/{self.lead.id}/')
        corbeille_id = r.data['corbeille_id']
        # Il apparaît dans la fenêtre d'undo de la corbeille (société courante).
        r = api.get('/api/django/core/corbeille/?undo=1')
        undo_ids = [row['id'] for row in r.data]
        self.assertIn(corbeille_id, undo_ids)
        # Restauration via le TrashViewSet partagé.
        rest = api.post(f'/api/django/core/corbeille/{corbeille_id}/restaurer/')
        self.assertEqual(rest.status_code, 200, rest.data)
        self.assertTrue(rest.data['restored'])
        # Le lead revient dans les querysets par défaut.
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.is_deleted)
        self.assertTrue(Lead.objects.filter(pk=self.lead.id).exists())
        r = api.get('/api/django/crm/leads/')
        self.assertIn(self.lead.id, ids_of(r))

    def test_restore_is_scoped_to_company(self):
        """La corbeille d'une autre société n'est jamais restaurable ici."""
        api = auth(self.admin)
        r = api.delete(f'/api/django/crm/leads/{self.lead.id}/')
        corbeille_id = r.data['corbeille_id']
        # Admin d'une AUTRE société : ne voit pas l'entrée, ne peut pas restaurer.
        other_company = make_company(slug='other-co', nom='Other Co')
        other_admin = User.objects.create_user(
            username='other_admin', password='x', role_legacy='admin',
            company=other_company,
        )
        other = auth(other_admin)
        r = other.get('/api/django/core/corbeille/?undo=1')
        self.assertNotIn(corbeille_id, [row['id'] for row in r.data])
        rest = other.post(
            f'/api/django/core/corbeille/{corbeille_id}/restaurer/')
        self.assertEqual(rest.status_code, 404)
        # Le lead d'origine reste supprimé (non restauré par la mauvaise société).
        self.assertTrue(Lead.all_objects.get(pk=self.lead.id).is_deleted)

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
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.is_deleted)
