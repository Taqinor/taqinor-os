"""Tests activités planifiées + pièces jointes (génériques)."""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.records.models import Activity, ActivityType, Attachment

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestActivities(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Act Co', slug='act-co')
        # Seed migration ne s'exécute pas sur la base de test fraîche par
        # société créée ici → on crée les types nous-mêmes.
        self.type_appel = ActivityType.objects.create(
            company=self.company, nom='Appel', ordre=10)
        self.user = User.objects.create_user(
            username='act_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Prospect')
        self.api = auth(self.user)

    def test_plan_then_list_for_record(self):
        resp = self.api.post('/api/django/records/activities/', {
            'model': 'crm.lead', 'id': self.lead.id,
            'activity_type': self.type_appel.id,
            'summary': 'Appeler le client', 'due_date': str(date.today()),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lst = self.api.get(
            f'/api/django/records/activities/?model=crm.lead&id={self.lead.id}')
        self.assertEqual(lst.status_code, 200)
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['state'], 'today')

    def test_mark_done_logs_historique_and_clears_open(self):
        act = Activity.objects.create(
            company=self.company,
            content_type=_ct_lead(), object_id=self.lead.id,
            activity_type=self.type_appel, summary='Appel',
            due_date=date.today() - timedelta(days=1),
            assigned_to=self.user)
        resp = self.api.post(
            f'/api/django/records/activities/{act.id}/done/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        act.refresh_from_db()
        self.assertTrue(act.done)
        # Historique du lead reçoit une note « Activité faite ».
        notes = LeadActivity.objects.filter(lead=self.lead, kind='note')
        self.assertTrue(any('Appel' in (n.body or '') and 'faite' in (n.body or '')
                            for n in notes))
        # La carte ne montre plus d'activité ouverte.
        from apps.crm.serializers import LeadSerializer
        self.lead.refresh_from_db()
        ser = LeadSerializer(self.lead, context={'request': None})
        self.assertIsNone(ser.data['next_activity'])

    def test_mine_buckets(self):
        Activity.objects.create(
            company=self.company, content_type=_ct_lead(),
            object_id=self.lead.id, activity_type=self.type_appel,
            due_date=date.today() - timedelta(days=2), assigned_to=self.user)
        Activity.objects.create(
            company=self.company, content_type=_ct_lead(),
            object_id=self.lead.id, activity_type=self.type_appel,
            due_date=date.today() + timedelta(days=5), assigned_to=self.user)
        resp = self.api.get('/api/django/records/activities/mine/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['en_retard']), 1)
        self.assertEqual(len(resp.data['a_venir']), 1)

    def test_relance_date_creates_activity(self):
        # Poser une relance via l'API lead crée l'activité Relance auto.
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.id}/',
            {'relance_date': str(date.today() + timedelta(days=7))},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        act = Activity.objects.filter(
            content_type=_ct_lead(), object_id=self.lead.id,
            auto_relance=True, done=False).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.due_date, date.today() + timedelta(days=7))

    def test_cross_company_target_rejected(self):
        other = Company.objects.create(nom='Other', slug='other-act')
        other_lead = Lead.objects.create(company=other, nom='Etranger')
        resp = self.api.post('/api/django/records/activities/', {
            'model': 'crm.lead', 'id': other_lead.id,
            'activity_type': self.type_appel.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class TestAttachments(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Att Co', slug='att-co')
        self.user = User.objects.create_user(
            username='att_resp', password='x', role_legacy='responsable',
            company=self.company)
        from apps.roles.models import Role, ALL_PERMISSIONS
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='att_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Doc Lead')
        self.api = auth(self.user)

    def test_upload_roundtrip_and_delete(self):
        from io import BytesIO
        png = (b'\x89PNG\r\n\x1a\n' + b'\x00' * 64)

        def fake_store(file):
            return ({'file_key': 'attachments/test.png',
                     'filename': 'test.png', 'size': len(png),
                     'mime': 'image/png'}, None)

        with mock.patch('apps.records.views.store_attachment', side_effect=fake_store):
            up = BytesIO(png)
            up.name = 'test.png'
            resp = self.api.post('/api/django/records/attachments/', {
                'model': 'crm.lead', 'id': self.lead.id, 'file': up,
            }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        att_id = resp.data['id']
        # Listé pour le record.
        lst = self.api.get(
            f'/api/django/records/attachments/?model=crm.lead&id={self.lead.id}')
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)
        # Compteur badge.
        cnt = self.api.get(
            f'/api/django/records/attachments-count/?model=crm.lead&id={self.lead.id}')
        self.assertEqual(cnt.data['count'], 1)
        # Commerciale ne peut PAS supprimer (admin only).
        with mock.patch('apps.records.views.delete_attachment'):
            d1 = self.api.delete(f'/api/django/records/attachments/{att_id}/')
            self.assertEqual(d1.status_code, 403)
            d2 = auth(self.admin).delete(
                f'/api/django/records/attachments/{att_id}/')
            self.assertEqual(d2.status_code, 204)
        self.assertFalse(Attachment.objects.filter(id=att_id).exists())

    def test_download_via_same_origin_endpoint(self):
        """B1 — l'URL servie est l'endpoint Django MÊME ORIGINE (pas une URL
        MinIO interne) et le téléchargement renvoie bien les octets + le type."""
        from io import BytesIO
        pdf = b'%PDF-1.4\n%%EOF\n'

        def fake_store(file):
            return ({'file_key': 'attachments/rt.pdf', 'filename': 'rt.pdf',
                     'size': len(pdf), 'mime': 'application/pdf'}, None)

        with mock.patch('apps.records.views.store_attachment',
                        side_effect=fake_store):
            up = BytesIO(pdf)
            up.name = 'rt.pdf'
            resp = self.api.post('/api/django/records/attachments/', {
                'model': 'crm.lead', 'id': self.lead.id, 'file': up,
            }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        att_id = resp.data['id']
        # L'URL n'est PAS une URL MinIO : c'est le proxy Django même origine.
        self.assertEqual(
            resp.data['url'],
            f'/api/django/records/attachments/{att_id}/download/')
        # Le proxy renvoie les octets stockés avec le bon Content-Type.
        with mock.patch('apps.records.views.fetch_attachment',
                        return_value=(pdf, None)):
            dl = self.api.get(
                f'/api/django/records/attachments/{att_id}/download/')
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl['Content-Type'], 'application/pdf')
        self.assertEqual(dl.content, pdf)

    def test_download_missing_object_returns_404(self):
        """Objet introuvable → 404 propre (jamais d'icône cassée silencieuse)."""
        att = Attachment.objects.create(
            company=self.company, content_type=_ct_lead(),
            object_id=self.lead.id, uploaded_by=self.user,
            file_key='attachments/none.pdf', filename='none.pdf',
            size=1, mime='application/pdf')
        with mock.patch('apps.records.views.fetch_attachment',
                        return_value=(None, 'Fichier introuvable.')):
            dl = self.api.get(
                f'/api/django/records/attachments/{att.id}/download/')
        self.assertEqual(dl.status_code, 404)


def _ct_lead():
    from django.contrib.contenttypes.models import ContentType
    return ContentType.objects.get_for_model(Lead)
