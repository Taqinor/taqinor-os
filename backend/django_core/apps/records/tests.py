"""Tests activités planifiées + pièces jointes (génériques)."""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.records.models import Activity, ActivityType, Attachment, Comment, Tag, TaggedItem

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

    def test_set_phase_retags_attachment(self):
        """L5 — déplacer une pièce jointe entre phases (avant/pendant/après)
        sans supprimer/ré-uploader : le re-tag persiste, scopé société."""
        from apps.installations.models import Installation
        from apps.crm.models import Client
        from django.contrib.contenttypes.models import ContentType
        client = Client.objects.create(company=self.company, nom='Cli Phase')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-PHASE', client=client)
        ct = ContentType.objects.get_for_model(Installation)
        att = Attachment.objects.create(
            company=self.company, content_type=ct, object_id=inst.id,
            uploaded_by=self.user, phase='avant',
            file_key='attachments/p.png', filename='p.png',
            size=1, mime='image/png')
        # Re-tag avant → apres.
        r = self.api.patch(
            f'/api/django/records/attachments/{att.id}/phase/',
            {'phase': 'apres'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        att.refresh_from_db()
        self.assertEqual(att.phase, 'apres')
        self.assertEqual(r.data['phase'], 'apres')
        # Phase invalide refusée.
        r2 = self.api.patch(
            f'/api/django/records/attachments/{att.id}/phase/',
            {'phase': 'n_importe_quoi'}, format='json')
        self.assertEqual(r2.status_code, 400, r2.data)

    def test_set_phase_cross_company_404(self):
        """Une autre société ne peut pas re-taguer une pièce jointe étrangère."""
        from apps.installations.models import Installation
        from apps.crm.models import Client
        from django.contrib.contenttypes.models import ContentType
        client = Client.objects.create(company=self.company, nom='Cli P2')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-P2', client=client)
        ct = ContentType.objects.get_for_model(Installation)
        att = Attachment.objects.create(
            company=self.company, content_type=ct, object_id=inst.id,
            uploaded_by=self.user, phase='avant',
            file_key='attachments/p2.png', filename='p2.png',
            size=1, mime='image/png')
        other = Company.objects.create(nom='Autre P', slug='autre-phase')
        ouser = User.objects.create_user(
            username='att_other', password='x', role_legacy='responsable',
            company=other)
        r = auth(ouser).patch(
            f'/api/django/records/attachments/{att.id}/phase/',
            {'phase': 'apres'}, format='json')
        self.assertEqual(r.status_code, 404, getattr(r, 'data', r))

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

    def test_upload_real_storage_persists_and_downloads(self):
        """N104 — régression : exerce le VRAI chemin de stockage (storage.py),
        pas un store mocké. Seul le client MinIO (boto3) est simulé par un
        backend objet en mémoire, donc la validation par octets magiques, la
        génération de clé et ``upload_fileobj``/``get_object`` s'exécutent
        réellement. On vérifie 201, la persistance de la ligne Attachment, puis
        que le proxy de téléchargement renvoie les octets exacts stockés."""
        from io import BytesIO
        png = (b'\x89PNG\r\n\x1a\n' + b'\x00' * 200)

        # Backend objet en mémoire : upload_fileobj écrit, get_object relit.
        objects = {}

        def _upload_fileobj(fileobj, bucket, key, **kwargs):
            objects[key] = fileobj.read()

        def _get_object(Bucket=None, Key=None):
            return {'Body': BytesIO(objects[Key])}

        fake_client = mock.MagicMock()
        fake_client.upload_fileobj.side_effect = _upload_fileobj
        fake_client.get_object.side_effect = _get_object

        with mock.patch('apps.records.storage.get_minio_client',
                        return_value=fake_client):
            up = BytesIO(png)
            up.name = 'preuve.png'
            resp = self.api.post('/api/django/records/attachments/', {
                'model': 'crm.lead', 'id': self.lead.id, 'file': up,
            }, format='multipart')
            self.assertEqual(resp.status_code, 201, resp.data)
            att_id = resp.data['id']

            # La ligne persiste, scopée société, avec les métadonnées réelles.
            att = Attachment.objects.get(id=att_id)
            self.assertEqual(att.company_id, self.company.id)
            self.assertEqual(att.mime, 'image/png')
            self.assertEqual(att.size, len(png))
            self.assertEqual(att.filename, 'preuve.png')
            self.assertTrue(att.file_key.startswith('attachments/'))
            self.assertTrue(att.file_key.endswith('.png'))
            # Le fichier a bien été téléversé dans le stockage objet.
            self.assertIn(att.file_key, objects)
            self.assertEqual(objects[att.file_key], png)

            # Le proxy de téléchargement (même origine) relit les octets exacts.
            self.assertEqual(
                resp.data['url'],
                f'/api/django/records/attachments/{att_id}/download/')
            dl = self.api.get(resp.data['url'])
            self.assertEqual(dl.status_code, 200)
            self.assertEqual(dl['Content-Type'], 'image/png')
            self.assertEqual(dl.content, png)

    def test_upload_rejects_unsupported_type_real_storage(self):
        """N104 — la validation par octets magiques (storage.py réel) refuse un
        binaire non supporté avec un 400 FR, sans rien téléverser."""
        from io import BytesIO
        bogus = b'PK\x03\x04 ceci est une archive zip, pas une image'

        fake_client = mock.MagicMock()
        with mock.patch('apps.records.storage.get_minio_client',
                        return_value=fake_client):
            up = BytesIO(bogus)
            up.name = 'archive.zip'
            resp = self.api.post('/api/django/records/attachments/', {
                'model': 'crm.lead', 'id': self.lead.id, 'file': up,
            }, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(fake_client.upload_fileobj.called)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_upload_self_heals_absent_bucket(self):
        """N108 — un upload réussit même si le bucket erp-uploads n'existe pas
        encore : ensure_uploads_bucket le crée (head_bucket échoue →
        create_bucket) juste avant le téléversement, au lieu de renvoyer un 500
        NoSuchBucket comme en production."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.records.storage import store_attachment

        pdf = SimpleUploadedFile(
            'doc.pdf', b'%PDF-1.4 contenu de test', content_type='application/pdf')

        fake_client = mock.MagicMock()
        # Bucket absent : head_bucket lève, comme le ferait MinIO (NoSuchBucket).
        fake_client.head_bucket.side_effect = Exception('NoSuchBucket')

        # ensure_uploads_bucket appelle get_minio_client depuis SON module ; on
        # patche les deux références pour ne jamais toucher un vrai stockage.
        with mock.patch('apps.records.storage.get_minio_client',
                        return_value=fake_client), \
                mock.patch('apps.ventes.utils.minio_client.get_minio_client',
                           return_value=fake_client):
            result, err = store_attachment(pdf)

        self.assertIsNone(err)
        self.assertIsNotNone(result)
        self.assertEqual(result['mime'], 'application/pdf')
        # Le bucket manquant a été auto-créé avant le téléversement…
        fake_client.create_bucket.assert_called_once()
        # …puis le fichier a bien été téléversé.
        self.assertTrue(fake_client.upload_fileobj.called)


def _ct_lead():
    from django.contrib.contenttypes.models import ContentType
    return ContentType.objects.get_for_model(Lead)


class TestResolveTargetErrors(TestCase):
    """ERR56 — un `model` valide + `id` inexistant ou de mauvais type doit
    produire une 400/200-vide propre (jamais un 500 non rattrapé)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Res Co', slug='res-co')
        self.type_appel = ActivityType.objects.create(
            company=self.company, nom='Appel', ordre=10)
        self.user = User.objects.create_user(
            username='res_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_resolve_target_nonexistent_pk_raises_valueerror(self):
        from apps.records.serializers import resolve_target
        with self.assertRaises(ValueError):
            resolve_target('crm.lead', 999999, self.company)

    def test_resolve_target_bad_type_pk_raises_valueerror(self):
        from apps.records.serializers import resolve_target
        with self.assertRaises(ValueError):
            resolve_target('crm.lead', 'pas-un-entier', self.company)

    def test_create_activity_nonexistent_target_is_400_not_500(self):
        resp = self.api.post('/api/django/records/activities/', {
            'model': 'crm.lead', 'id': 999999,
            'activity_type': self.type_appel.id, 'summary': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))

    def test_create_activity_bad_type_id_is_400_not_500(self):
        resp = self.api.post('/api/django/records/activities/', {
            'model': 'crm.lead', 'id': 'pas-un-entier',
            'activity_type': self.type_appel.id, 'summary': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))

    def test_list_activities_nonexistent_target_is_clean_empty(self):
        resp = self.api.get(
            '/api/django/records/activities/?model=crm.lead&id=999999')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        data = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(data), 0)

    def test_attachments_count_bad_type_id_is_clean_zero(self):
        resp = self.api.get(
            '/api/django/records/attachments-count/'
            '?model=crm.lead&id=pas-un-entier')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(resp.data['count'], 0)


class TestVentesAttachmentTargets(TestCase):
    """ventes.devis et ventes.facture sont des cibles de pièce jointe valides :
    on peut RÉELLEMENT y joindre un fichier (persiste + listable)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Vts Att', slug='vts-att')
        from apps.roles.models import Role, COMMERCIAL_PERMISSIONS
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.user = User.objects.create_user(
            username='vts_com', password='x', role=role, company=self.company)
        self.api = auth(self.user)

    def _client(self):
        from apps.crm.models import Client
        return Client.objects.create(company=self.company, nom='Cli VA')

    def _upload(self, model, oid):
        from io import BytesIO
        pdf = b'%PDF-1.4\n%%EOF\n'

        def fake_store(file):
            return ({'file_key': f'attachments/{model}.pdf',
                     'filename': 'piece.pdf', 'size': len(pdf),
                     'mime': 'application/pdf'}, None)

        with mock.patch('apps.records.views.store_attachment',
                        side_effect=fake_store):
            up = BytesIO(pdf)
            up.name = 'piece.pdf'
            return self.api.post('/api/django/records/attachments/', {
                'model': model, 'id': oid, 'file': up,
            }, format='multipart')

    def test_attach_to_devis(self):
        from apps.ventes.models import Devis
        devis = Devis.objects.create(
            company=self.company, reference='DEV-VA-1', client=self._client())
        resp = self._upload('ventes.devis', devis.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Attachment.objects.filter(object_id=str(devis.id)).count(), 1)
        lst = self.api.get(
            f'/api/django/records/attachments/?model=ventes.devis&id={devis.id}')
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)

    def test_attach_to_facture(self):
        from apps.ventes.models import Facture
        facture = Facture.objects.create(
            company=self.company, reference='FAC-VA-1', client=self._client())
        resp = self._upload('ventes.facture', facture.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            Attachment.objects.filter(object_id=str(facture.id)).count(), 1)


class TestComments(TestCase):
    """FG7 — Commentaires génériques + @mentions."""

    def setUp(self):
        self.company = Company.objects.create(nom='Cmt Co', slug='cmt-co')
        self.resp = User.objects.create_user(
            username='cmt_resp', password='x', role_legacy='responsable',
            company=self.company)
        from apps.roles.models import Role, ALL_PERMISSIONS
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='cmt_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead Cmt')
        self.api = auth(self.resp)

    def test_create_and_list_comment(self):
        res = self.api.post('/api/django/records/comments/', {
            'model': 'crm.lead', 'id': self.lead.id,
            'body': 'Premier commentaire.',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['body'], 'Premier commentaire.')
        self.assertEqual(res.data['author_username'], 'cmt_resp')
        # Liste filtrée par record.
        lst = self.api.get(
            f'/api/django/records/comments/?model=crm.lead&id={self.lead.id}')
        self.assertEqual(lst.status_code, 200)
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)

    def test_mention_notifies_user(self):
        """@mention dans un commentaire → notification in-app pour l'utilisateur mentionné."""
        from apps.notifications.models import EventType, Notification
        # L'admin s'appelle 'cmt_admin'. Le responsable le mentionne.
        res = self.api.post('/api/django/records/comments/', {
            'model': 'crm.lead', 'id': self.lead.id,
            'body': 'Bonjour @cmt_admin, peux-tu vérifier ?',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        notifs = Notification.objects.filter(recipient=self.admin)
        self.assertGreater(notifs.count(), 0)
        notif = notifs.first()
        self.assertIn('cmt_resp', notif.title)

    def test_mention_own_name_no_self_notification(self):
        """@auto-mention → pas de notification envoyée à soi-même."""
        from apps.notifications.models import Notification
        self.api.post('/api/django/records/comments/', {
            'model': 'crm.lead', 'id': self.lead.id,
            'body': '@cmt_resp je me rappelle à moi-même.',
        }, format='json')
        self.assertEqual(
            Notification.objects.filter(recipient=self.resp).count(), 0)

    def test_delete_by_admin(self):
        """L'admin peut supprimer n'importe quel commentaire."""
        res = self.api.post('/api/django/records/comments/', {
            'model': 'crm.lead', 'id': self.lead.id,
            'body': 'À supprimer.',
        }, format='json')
        cmt_id = res.data['id']
        # Le responsable (auteur) ne peut pas supprimer (admin only).
        d1 = self.api.delete(f'/api/django/records/comments/{cmt_id}/')
        self.assertEqual(d1.status_code, 403)
        # L'admin peut.
        d2 = auth(self.admin).delete(f'/api/django/records/comments/{cmt_id}/')
        self.assertEqual(d2.status_code, 204)
        self.assertFalse(Comment.objects.filter(id=cmt_id).exists())

    def test_cross_company_target_rejected(self):
        """Commenter un enregistrement étranger → 400."""
        other = Company.objects.create(nom='Other Cmt', slug='other-cmt')
        other_lead = Lead.objects.create(company=other, nom='Prospect autre')
        res = self.api.post('/api/django/records/comments/', {
            'model': 'crm.lead', 'id': other_lead.id,
            'body': 'Commentaire interdit.',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_company_scoped_listing(self):
        """Un utilisateur ne voit que les commentaires de sa société."""
        from django.contrib.contenttypes.models import ContentType
        other = Company.objects.create(nom='Other Cmt2', slug='other-cmt2')
        other_lead = Lead.objects.create(company=other, nom='Lead Autre')
        ct = ContentType.objects.get_for_model(Lead)
        # Commentaire inséré directement pour l'autre société.
        Comment.objects.create(
            company=other, content_type=ct, object_id=other_lead.id,
            body='Commentaire autre société.', author=None)
        # Notre commentaire.
        self.api.post('/api/django/records/comments/', {
            'model': 'crm.lead', 'id': self.lead.id, 'body': 'Mon commentaire.',
        }, format='json')
        lst = self.api.get('/api/django/records/comments/')
        data = lst.data['results'] if 'results' in lst.data else lst.data
        # On ne voit que le nôtre.
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['body'], 'Mon commentaire.')


class TestTags(TestCase):
    """FG9 — Vocabulaire de tags partagés + TaggedItems."""

    def setUp(self):
        self.company = Company.objects.create(nom='Tag Co', slug='tag-co')
        self.resp = User.objects.create_user(
            username='tag_resp', password='x', role_legacy='responsable',
            company=self.company)
        from apps.roles.models import Role, ALL_PERMISSIONS
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='tag_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead Tag')
        self.api = auth(self.resp)

    def test_create_and_list_tags(self):
        res = auth(self.admin).post('/api/django/records/tags/', {
            'nom': 'Priorité haute', 'couleur': '#ef4444',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['nom'], 'Priorité haute')
        self.assertEqual(Tag.objects.filter(company=self.company).count(), 1)
        # La liste est visible par tout rôle.
        lst = self.api.get('/api/django/records/tags/')
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)

    def test_tag_scoped_per_company(self):
        """Les tags d'une société ne sont pas visibles par une autre."""
        other = Company.objects.create(nom='Other Tag', slug='other-tag')
        Tag.objects.create(company=other, nom='Tag Autre')
        Tag.objects.create(company=self.company, nom='Tag Nôtre')
        lst = self.api.get('/api/django/records/tags/')
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['nom'], 'Tag Nôtre')

    def test_apply_and_list_tagged_items(self):
        """Appliquer un tag à un enregistrement et le retrouver par filtrage."""
        tag = Tag.objects.create(company=self.company, nom='Important')
        res = self.api.post('/api/django/records/tagged-items/', {
            'model': 'crm.lead', 'id': self.lead.id, 'tag': tag.id,
        }, format='json')
        self.assertIn(res.status_code, (200, 201))
        self.assertEqual(TaggedItem.objects.count(), 1)
        # Liste filtrée par record.
        lst = self.api.get(
            f'/api/django/records/tagged-items/?model=crm.lead&id={self.lead.id}')
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['tag_nom'], 'Important')

    def test_apply_tag_is_idempotent(self):
        """Appliquer le même tag deux fois → une seule ligne TaggedItem."""
        tag = Tag.objects.create(company=self.company, nom='Idempotent')
        self.api.post('/api/django/records/tagged-items/', {
            'model': 'crm.lead', 'id': self.lead.id, 'tag': tag.id,
        }, format='json')
        self.api.post('/api/django/records/tagged-items/', {
            'model': 'crm.lead', 'id': self.lead.id, 'tag': tag.id,
        }, format='json')
        self.assertEqual(TaggedItem.objects.count(), 1)

    def test_remove_tagged_item(self):
        """Retirer un tag d'un enregistrement (DELETE TaggedItem)."""
        tag = Tag.objects.create(company=self.company, nom='À retirer')
        res = self.api.post('/api/django/records/tagged-items/', {
            'model': 'crm.lead', 'id': self.lead.id, 'tag': tag.id,
        }, format='json')
        item_id = res.data['id']
        d = self.api.delete(f'/api/django/records/tagged-items/{item_id}/')
        self.assertEqual(d.status_code, 204)
        self.assertEqual(TaggedItem.objects.count(), 0)

    def test_foreign_tag_rejected(self):
        """Appliquer un tag d'une autre société → 400."""
        other = Company.objects.create(nom='Other T2', slug='other-t2')
        foreign_tag = Tag.objects.create(company=other, nom='Tag Étranger')
        res = self.api.post('/api/django/records/tagged-items/', {
            'model': 'crm.lead', 'id': self.lead.id, 'tag': foreign_tag.id,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_tag_search_filter(self):
        """Le filtre ?q= sur /records/tags/ filtre par nom (insensible à la casse)."""
        Tag.objects.create(company=self.company, nom='Solar VIP')
        Tag.objects.create(company=self.company, nom='Résidentiel')
        res = self.api.get('/api/django/records/tags/?q=solar')
        data = res.data['results'] if 'results' in res.data else res.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['nom'], 'Solar VIP')


class TestAttachmentsAll(TestCase):
    """FG10 — Centre de pièces jointes de la société (GET records/attachments/all/)."""

    def setUp(self):
        self.company = Company.objects.create(nom='AttAll Co', slug='attall-co')
        self.user = User.objects.create_user(
            username='attall_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead AttAll')
        self.api = auth(self.user)

    def _make_att(self, filename, mime='application/pdf', phase=''):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Lead)
        return Attachment.objects.create(
            company=self.company, content_type=ct, object_id=self.lead.id,
            uploaded_by=self.user, file_key=f'attachments/{filename}',
            filename=filename, size=1, mime=mime, phase=phase)

    def test_all_returns_company_attachments(self):
        """L'endpoint retourne toutes les pièces jointes de la société."""
        self._make_att('doc1.pdf')
        self._make_att('doc2.pdf')
        res = self.api.get('/api/django/records/attachments/all/')
        self.assertEqual(res.status_code, 200, res.data)
        count = res.data.get('count', len(res.data))
        self.assertEqual(count, 2)

    def test_mime_filter(self):
        """Filtre ?mime= filtre exactement sur le type MIME."""
        self._make_att('img.png', mime='image/png')
        self._make_att('doc.pdf', mime='application/pdf')
        res = self.api.get('/api/django/records/attachments/all/?mime=image/png')
        data = res.data.get('results', res.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['filename'], 'img.png')

    def test_mime_like_filter(self):
        """Filtre ?mime_like=image filtre tous les types image/*."""
        self._make_att('img.png', mime='image/png')
        self._make_att('img2.jpg', mime='image/jpeg')
        self._make_att('doc.pdf', mime='application/pdf')
        res = self.api.get('/api/django/records/attachments/all/?mime_like=image')
        data = res.data.get('results', res.data)
        self.assertEqual(len(data), 2)

    def test_phase_filter(self):
        """Filtre ?phase= filtre sur la phase (avant/pendant/apres)."""
        self._make_att('avant.pdf', phase='avant')
        self._make_att('apres.pdf', phase='apres')
        self._make_att('sans_phase.pdf', phase='')
        res = self.api.get('/api/django/records/attachments/all/?phase=avant')
        data = res.data.get('results', res.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['filename'], 'avant.pdf')

    def test_model_filter(self):
        """Filtre ?model= filtre sur le content_type."""
        from apps.crm.models import Client
        from django.contrib.contenttypes.models import ContentType
        self._make_att('lead.pdf')
        # PJ sur un Client.
        cli = Client.objects.create(company=self.company, nom='Cli All')
        ct_cli = ContentType.objects.get_for_model(Client)
        Attachment.objects.create(
            company=self.company, content_type=ct_cli, object_id=cli.id,
            uploaded_by=self.user, file_key='attachments/cli.pdf',
            filename='cli.pdf', size=1, mime='application/pdf')
        res = self.api.get('/api/django/records/attachments/all/?model=crm.lead')
        data = res.data.get('results', res.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['filename'], 'lead.pdf')

    def test_cross_company_isolation(self):
        """Les pièces jointes d'une autre société ne sont jamais retournées."""
        from django.contrib.contenttypes.models import ContentType
        other = Company.objects.create(nom='Other All', slug='other-all')
        other_lead = Lead.objects.create(company=other, nom='Lead Other')
        ct = ContentType.objects.get_for_model(Lead)
        Attachment.objects.create(
            company=other, content_type=ct, object_id=other_lead.id,
            uploaded_by=None, file_key='attachments/other.pdf',
            filename='other.pdf', size=1, mime='application/pdf')
        self._make_att('mine.pdf')
        res = self.api.get('/api/django/records/attachments/all/')
        data = res.data.get('results', res.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['filename'], 'mine.pdf')
