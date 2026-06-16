"""Tests des actions en masse (T3), recherche globale + notifications (T5)."""
from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity

User = get_user_model()


def make_company(slug='bulk-co', nom='Bulk Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class _Base(TestCase):
    def setUp(self):
        from apps.roles.models import Role, ALL_PERMISSIONS
        self.company = make_company()
        self.other = make_company(slug='bulk-other', nom='Bulk Other')
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='bulk_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.resp = User.objects.create_user(
            username='bulk_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = self._api(self.resp)
        self.admin_api = self._api(self.admin)

    def _api(self, u):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(u)}')
        return api

    def _bulk(self, action, ids, params=None, api=None):
        return (api or self.api).post(
            '/api/django/crm/leads/bulk/',
            {'action': action, 'ids': ids, 'params': params or {}},
            format='json')


class TestBulkActions(_Base):
    def test_reassign_logs_en_masse(self):
        leads = [Lead.objects.create(company=self.company, nom=f'L{i}')
                 for i in range(3)]
        ids = [le.id for le in leads]
        r = self._bulk('reassign', ids, {'owner': self.admin.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['updated'], 3)
        for le in leads:
            le.refresh_from_db()
            self.assertEqual(le.owner_id, self.admin.id)
        act = LeadActivity.objects.filter(
            lead=leads[0], field='owner').first()
        self.assertIsNotNone(act)
        self.assertIn('en masse', act.body)

    def test_add_and_remove_tag(self):
        le = Lead.objects.create(company=self.company, nom='Tagged',
                                 tags='VIP')
        self._bulk('add_tag', [le.id], {'tag': 'Urgent'})
        le.refresh_from_db()
        self.assertIn('Urgent', le.tags)
        self.assertIn('VIP', le.tags)
        self._bulk('remove_tag', [le.id], {'tag': 'VIP'})
        le.refresh_from_db()
        self.assertNotIn('VIP', le.tags)
        self.assertIn('Urgent', le.tags)

    def test_change_stage_forward_ok(self):
        le = Lead.objects.create(company=self.company, nom='Forward')
        r = self._bulk('change_stage', [le.id], {'stage': 'CONTACTED'})
        self.assertEqual(r.status_code, 200)
        le.refresh_from_db()
        self.assertEqual(le.stage, 'CONTACTED')
        self.assertEqual(r.data['updated'], 1)

    def test_change_stage_backward_blocked(self):
        le = Lead.objects.create(company=self.company, nom='Back',
                                 stage='QUOTE_SENT')
        r = self._bulk('change_stage', [le.id], {'stage': 'NEW'})
        self.assertEqual(r.status_code, 200)
        le.refresh_from_db()
        self.assertEqual(le.stage, 'QUOTE_SENT')  # inchangé
        self.assertEqual(r.data['updated'], 0)
        self.assertTrue(r.data['warnings'])

    def test_change_stage_skips_perdu(self):
        le = Lead.objects.create(company=self.company, nom='Perdu',
                                 stage='NEW', perdu=True)
        r = self._bulk('change_stage', [le.id], {'stage': 'CONTACTED'})
        le.refresh_from_db()
        self.assertEqual(le.stage, 'NEW')
        self.assertEqual(r.data['updated'], 0)

    def test_reactivate_cold_like_single_edit(self):
        le = Lead.objects.create(company=self.company, nom='Froid',
                                 stage='COLD')
        r = self._bulk('change_stage', [le.id], {'stage': 'FOLLOW_UP'})
        le.refresh_from_db()
        self.assertEqual(le.stage, 'FOLLOW_UP')
        self.assertEqual(r.data['updated'], 1)

    def test_set_and_clear_relance(self):
        le = Lead.objects.create(company=self.company, nom='Relance')
        self._bulk('set_relance', [le.id], {'relance_date': '2026-07-01'})
        le.refresh_from_db()
        self.assertEqual(str(le.relance_date), '2026-07-01')
        self._bulk('clear_relance', [le.id])
        le.refresh_from_db()
        self.assertIsNone(le.relance_date)

    def test_flag_and_unflag_perdu(self):
        le = Lead.objects.create(company=self.company, nom='Lost')
        self._bulk('flag_perdu', [le.id], {'motif_perte': 'Trop cher'})
        le.refresh_from_db()
        self.assertTrue(le.perdu)
        self.assertEqual(le.motif_perte, 'Trop cher')
        self._bulk('unflag_perdu', [le.id])
        le.refresh_from_db()
        self.assertFalse(le.perdu)

    def test_archive_unarchive(self):
        le = Lead.objects.create(company=self.company, nom='Arch')
        self._bulk('archive', [le.id])
        le.refresh_from_db()
        self.assertTrue(le.is_archived)
        self._bulk('unarchive', [le.id])
        le.refresh_from_db()
        self.assertFalse(le.is_archived)

    def test_foreign_ids_ignored(self):
        mine = Lead.objects.create(company=self.company, nom='Mine')
        theirs = Lead.objects.create(company=self.other, nom='Theirs')
        r = self._bulk('archive', [mine.id, theirs.id])
        self.assertEqual(r.data['matched'], 1)
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_archived)

    def test_delete_admin_only(self):
        le = Lead.objects.create(company=self.company, nom='Del')
        r = self._bulk('delete', [le.id])  # responsable
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Lead.objects.filter(pk=le.id).exists())
        r = self._bulk('delete', [le.id], api=self.admin_api)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(Lead.objects.filter(pk=le.id).exists())

    def test_delete_blocked_when_orphaning_devis(self):
        from apps.ventes.models import Devis
        cl = Client.objects.create(company=self.company, nom='C')
        le = Lead.objects.create(company=self.company, nom='HasDevis')
        Devis.objects.create(
            company=self.company, reference='DEV-BULK-0001',
            client=cl, lead=le, statut='brouillon')
        r = self._bulk('delete', [le.id], api=self.admin_api)
        self.assertEqual(r.status_code, 409)
        self.assertTrue(Lead.objects.filter(pk=le.id).exists())

    def test_export_returns_xlsx(self):
        Lead.objects.create(company=self.company, nom='Export Me')
        le = Lead.objects.create(company=self.company, nom='Export2')
        r = self._bulk('export', [le.id])
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertTrue(r.content[:2] == b'PK')  # zip/xlsx magic

    def test_empty_selection_rejected(self):
        r = self._bulk('archive', [])
        self.assertEqual(r.status_code, 400)

    def test_unknown_action_rejected(self):
        le = Lead.objects.create(company=self.company, nom='X')
        r = self._bulk('frobnicate', [le.id])
        self.assertEqual(r.status_code, 400)


class TestGlobalSearch(_Base):
    def test_search_groups_leads_and_clients(self):
        Lead.objects.create(company=self.company, nom='Zaytoun', ville='Fès')
        Client.objects.create(company=self.company, nom='Zaytoun Corp')
        Lead.objects.create(company=self.other, nom='Zaytoun Foreign')
        r = self.api.get('/api/django/crm/search/?q=Zaytoun')
        self.assertEqual(r.status_code, 200)
        types = {g['type']: g for g in r.data['groups']}
        self.assertIn('leads', types)
        self.assertIn('clients', types)
        # Scope société : le lead étranger n'apparaît pas.
        labels = [it['label'] for it in types['leads']['items']]
        self.assertTrue(any('Zaytoun' in lbl for lbl in labels))
        self.assertFalse(any('Foreign' in lbl for lbl in labels))

    def test_empty_query_returns_no_groups(self):
        r = self.api.get('/api/django/crm/search/?q=')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['groups'], [])

    def test_lead_route_hint(self):
        le = Lead.objects.create(company=self.company, nom='Routable')
        r = self.api.get('/api/django/crm/search/?q=Routable')
        leads = next(g for g in r.data['groups'] if g['type'] == 'leads')
        self.assertEqual(leads['items'][0]['route'], f'/crm/leads?lead={le.id}')


class TestNotifications(_Base):
    def test_overdue_activity_counted(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Activity, ActivityType
        le = Lead.objects.create(company=self.company, nom='Late')
        atype = ActivityType.objects.create(
            company=self.company, nom='Relance')
        ct = ContentType.objects.get_for_model(Lead)
        Activity.objects.create(
            company=self.company, content_type=ct, object_id=le.id,
            activity_type=atype, summary='Rappeler',
            due_date=date.today() - timedelta(days=3), done=False)
        r = self.api.get('/api/django/crm/notifications/')
        self.assertEqual(r.status_code, 200)
        types = {g['type']: g for g in r.data['groups']}
        self.assertIn('overdue_activities', types)
        self.assertEqual(types['overdue_activities']['count'], 1)
        self.assertGreaterEqual(r.data['total'], 1)

    def test_overdue_invoice_counted(self):
        from apps.ventes.models import Facture
        cl = Client.objects.create(company=self.company, nom='Payeur')
        Facture.objects.create(
            company=self.company, reference='FAC-NOTIF-0001',
            client=cl, statut='en_retard',
            date_echeance=date.today() - timedelta(days=30))
        r = self.api.get('/api/django/crm/notifications/')
        types = {g['type']: g for g in r.data['groups']}
        self.assertIn('overdue_invoices', types)
        self.assertEqual(types['overdue_invoices']['count'], 1)

    def test_notifications_company_scoped(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Activity, ActivityType
        le = Lead.objects.create(company=self.other, nom='Foreign Late')
        atype = ActivityType.objects.create(company=self.other, nom='R')
        ct = ContentType.objects.get_for_model(Lead)
        Activity.objects.create(
            company=self.other, content_type=ct, object_id=le.id,
            activity_type=atype, summary='x',
            due_date=date.today() - timedelta(days=3), done=False)
        r = self.api.get('/api/django/crm/notifications/')
        self.assertEqual(r.data['total'], 0)
