"""Tests des actions EN MASSE sur les leads (T3) + export Excel.

Couvre : multi-tenant (jamais hors société), règles du funnel (jamais en
arrière, jamais un lead Perdu, réactivation du Froid), journal Historique
marqué « en masse », garde-fous (devis liés bloquent la suppression, delete
réservé à l'admin) et l'export .xlsx d'une sélection.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead, LeadActivity
from authentication.models import Company

User = get_user_model()


def make_company(slug='bulk-co', nom='Bulk Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BulkLeadsBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.resp = User.objects.create_user(
            username='bulk_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.admin = User.objects.create_user(
            username='bulk_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self._auth(self.resp)

    def _auth(self, user):
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def mk(self, **kw):
        kw.setdefault('company', self.company)
        kw.setdefault('nom', 'Lead')
        return Lead.objects.create(**kw)

    def bulk(self, **payload):
        return self.api.post('/api/django/crm/leads/bulk/', payload, format='json')


class TestBulkReassignTag(BulkLeadsBase):
    def test_reassign_owner_logs_en_masse(self):
        a, b = self.mk(nom='A'), self.mk(nom='B')
        owner = User.objects.create_user(
            username='cible', password='x', role_legacy='responsable',
            company=self.company)
        resp = self.bulk(action='reassign', ids=[a.id, b.id], owner=owner.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 2)
        a.refresh_from_db()
        self.assertEqual(a.owner_id, owner.id)
        act = LeadActivity.objects.filter(lead=a, field='owner').first()
        self.assertIsNotNone(act)
        self.assertTrue(act.bulk)

    def test_add_then_remove_tag(self):
        a = self.mk(nom='A', tags='Solaire')
        self.bulk(action='add_tag', ids=[a.id], tag='VIP')
        a.refresh_from_db()
        self.assertIn('VIP', a.tags)
        self.assertIn('Solaire', a.tags)
        # Ré-ajouter le même tag ne duplique pas (compté inchangé).
        again = self.bulk(action='add_tag', ids=[a.id], tag='VIP')
        self.assertEqual(again.data['unchanged'], 1)
        self.bulk(action='remove_tag', ids=[a.id], tag='VIP')
        a.refresh_from_db()
        self.assertNotIn('VIP', a.tags)


class TestBulkStageFunnel(BulkLeadsBase):
    def test_no_backward_move(self):
        # QUOTE_SENT ne peut PAS reculer à NEW en masse.
        lead = self.mk(stage='QUOTE_SENT')
        resp = self.bulk(action='set_stage', ids=[lead.id], stage='NEW')
        self.assertEqual(resp.data['updated'], 0)
        self.assertEqual(len(resp.data['skipped']), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'QUOTE_SENT')

    def test_forward_move_logs(self):
        lead = self.mk(stage='NEW')
        resp = self.bulk(action='set_stage', ids=[lead.id], stage='CONTACTED')
        self.assertEqual(resp.data['updated'], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'CONTACTED')
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead, field='stage', bulk=True).exists())

    def test_cold_is_reactivated(self):
        lead = self.mk(stage='COLD')
        resp = self.bulk(action='set_stage', ids=[lead.id], stage='CONTACTED')
        self.assertEqual(resp.data['updated'], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'CONTACTED')

    def test_perdu_lead_never_moves(self):
        lead = self.mk(stage='NEW', perdu=True)
        resp = self.bulk(action='set_stage', ids=[lead.id], stage='SIGNED')
        self.assertEqual(resp.data['updated'], 0)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'NEW')

    def test_invalid_stage_rejected(self):
        lead = self.mk(stage='NEW')
        resp = self.bulk(action='set_stage', ids=[lead.id], stage='BOGUS')
        self.assertEqual(resp.status_code, 400)


class TestBulkRelancePerduArchive(BulkLeadsBase):
    def test_set_and_clear_relance(self):
        lead = self.mk()
        self.bulk(action='set_relance', ids=[lead.id], relance_date='2026-09-01')
        lead.refresh_from_db()
        self.assertEqual(lead.relance_date, date(2026, 9, 1))
        self.bulk(action='clear_relance', ids=[lead.id])
        lead.refresh_from_db()
        self.assertIsNone(lead.relance_date)

    def test_flag_and_unflag_perdu(self):
        lead = self.mk(stage='QUOTE_SENT')
        self.bulk(action='set_perdu', ids=[lead.id], motif='Prix trop élevé')
        lead.refresh_from_db()
        self.assertTrue(lead.perdu)
        self.assertEqual(lead.motif_perte, 'Prix trop élevé')
        # Le funnel ne bouge pas (Perdu est un drapeau, pas une étape).
        self.assertEqual(lead.stage, 'QUOTE_SENT')
        self.bulk(action='unset_perdu', ids=[lead.id])
        lead.refresh_from_db()
        self.assertFalse(lead.perdu)
        self.assertIsNone(lead.motif_perte)

    def test_archive_unarchive(self):
        lead = self.mk()
        self.bulk(action='archive', ids=[lead.id])
        lead.refresh_from_db()
        self.assertTrue(lead.is_archived)
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead, bulk=True, kind='note').exists())
        self.bulk(action='unarchive', ids=[lead.id])
        lead.refresh_from_db()
        self.assertFalse(lead.is_archived)


class TestBulkDeletePermissions(BulkLeadsBase):
    def test_delete_blocked_for_responsable(self):
        lead = self.mk()
        resp = self.bulk(action='delete', ids=[lead.id])
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Lead.objects.filter(id=lead.id).exists())

    def test_admin_delete_skips_leads_with_devis(self):
        self._auth(self.admin)
        free = self.mk(nom='Libre')
        linked = self.mk(nom='AvecDevis')
        from apps.ventes.models import Devis
        client = Client.objects.create(company=self.company, nom='C')
        Devis.objects.create(
            company=self.company, reference='DEV-BULK-1', client=client,
            lead=linked, taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        resp = self.bulk(action='delete', ids=[free.id, linked.id])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 1)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertFalse(Lead.objects.filter(id=free.id).exists())
        self.assertTrue(Lead.objects.filter(id=linked.id).exists())


class TestBulkTenantIsolation(BulkLeadsBase):
    def test_cannot_touch_other_company_leads(self):
        other = Company.objects.create(slug='other-bulk', nom='Autre')
        foreign = Lead.objects.create(company=other, nom='Étranger', stage='NEW')
        resp = self.bulk(action='set_stage', ids=[foreign.id], stage='SIGNED')
        # Le lead étranger n'est pas dans la société → ni vu, ni modifié.
        self.assertEqual(resp.data['total'], 0)
        foreign.refresh_from_db()
        self.assertEqual(foreign.stage, 'NEW')


class TestBulkExport(BulkLeadsBase):
    def test_export_xlsx_selection(self):
        a = self.mk(nom='Alaoui', prenom='Sara', stage='QUOTE_SENT')
        b = self.mk(nom='Bennani', stage='NEW')
        resp = self.api.post(
            '/api/django/crm/leads/export-xlsx/',
            {'ids': [a.id, b.id]}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        # Un .xlsx est un ZIP : signature PK.
        self.assertTrue(body.startswith(b'PK'))
        self.assertGreater(len(body), 2000)

    def test_export_requires_selection(self):
        resp = self.api.post(
            '/api/django/crm/leads/export-xlsx/', {'ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)


class TestBulkCanalPriorite(BulkLeadsBase):
    def test_set_canal_en_masse(self):
        a, b = self.mk(nom='A'), self.mk(nom='B')
        resp = self.bulk(action='set_canal', ids=[a.id, b.id], canal='reference')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 2)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.canal, 'reference')
        self.assertEqual(b.canal, 'reference')
        # Journal « en masse ».
        self.assertTrue(LeadActivity.objects.filter(
            lead=a, field='canal', bulk=True).exists())

    def test_set_canal_unknown_when_referential_exists(self):
        from apps.crm.models import Canal
        Canal.objects.create(company=self.company, cle='reference',
                             libelle='Référence')
        a = self.mk(nom='A')
        resp = self.bulk(action='set_canal', ids=[a.id], canal='inexistant')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_set_priorite_en_masse(self):
        a, b = self.mk(nom='A', priorite='normale'), self.mk(nom='B')
        resp = self.bulk(action='set_priorite', ids=[a.id, b.id], priorite='haute')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 2)
        a.refresh_from_db()
        self.assertEqual(a.priorite, 'haute')
        self.assertTrue(LeadActivity.objects.filter(
            lead=a, field='priorite', bulk=True).exists())

    def test_set_priorite_invalid(self):
        a = self.mk(nom='A')
        resp = self.bulk(action='set_priorite', ids=[a.id], priorite='extreme')
        self.assertEqual(resp.status_code, 400, resp.data)


class TestBulkPlanActivity(BulkLeadsBase):
    """L13 — « Planifier une activité » crée une activité ouverte par lead."""

    def test_plan_activity_creates_one_per_lead(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Activity
        a, b = self.mk(nom='A', owner=self.resp), self.mk(nom='B')
        resp = self.bulk(
            action='plan_activity', ids=[a.id, b.id],
            summary='Appeler demain', due_date='2026-07-01')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['updated'], 2)
        ct = ContentType.objects.get_for_model(Lead)
        for lead in (a, b):
            act = Activity.objects.filter(
                content_type=ct, object_id=lead.id, done=False).first()
            self.assertIsNotNone(act)
            self.assertEqual(act.summary, 'Appeler demain')
            self.assertEqual(act.due_date.isoformat(), '2026-07-01')
            self.assertEqual(act.company_id, self.company.id)
        # Le responsable du lead est l'assigné quand il existe.
        act_a = Activity.objects.filter(content_type=ct, object_id=a.id).first()
        self.assertEqual(act_a.assigned_to_id, self.resp.id)
        # Journal « en masse ».
        self.assertTrue(LeadActivity.objects.filter(lead=a, bulk=True).exists())

    def test_plan_activity_requires_summary_and_date(self):
        a = self.mk(nom='A')
        r1 = self.bulk(action='plan_activity', ids=[a.id], due_date='2026-07-01')
        self.assertEqual(r1.status_code, 400, r1.data)
        r2 = self.bulk(action='plan_activity', ids=[a.id], summary='X')
        self.assertEqual(r2.status_code, 400, r2.data)
