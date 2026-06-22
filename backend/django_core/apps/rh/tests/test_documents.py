"""Tests FG159 — coffre documents employé (records.Attachment + expiration).

Couvre : upload d'un document typé (réutilise le stockage records.Attachment,
mocké pour ne jamais toucher MinIO), expiration optionnelle (NULL accepté),
liste filtrée par employé, sélecteur « expire bientôt » (exclut sans-échéance
et déjà-expirés), société posée côté serveur + isolation entre sociétés, accès
réservé au palier Administrateur/Responsable (un « normal » est refusé), et
suppression qui efface aussi la pièce jointe.
"""
from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.records.models import Attachment
from apps.rh import selectors
from apps.rh.models import DocumentEmploye, DossierEmploye

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def _fake_store(file):
    return ({'file_key': 'attachments/doc.pdf', 'filename': 'contrat.pdf',
             'size': 1234, 'mime': 'application/pdf'}, None)


def _upload(api, employe_id, **extra):
    data = {'employe': employe_id, 'type_document': 'contrat'}
    data.update(extra)
    pdf = BytesIO(b'%PDF-1.4 fake')
    pdf.name = 'contrat.pdf'
    data['file'] = pdf
    with mock.patch('apps.rh.views.store_attachment', side_effect=_fake_store):
        return api.post('/api/django/rh/documents/', data, format='multipart')


class DocumentEmployeTests(TestCase):
    BASE = '/api/django/rh/documents/'

    def setUp(self):
        self.co_a = make_company('rh-doc-a', 'A')
        self.co_b = make_company('rh-doc-b', 'B')
        self.user_a = make_user(self.co_a, 'rh-doc-a')
        self.user_b = make_user(self.co_b, 'rh-doc-b')
        self.emp_a = DossierEmploye.objects.create(
            company=self.co_a, matricule='EMP-DOC-A', nom='Alami', prenom='Y')
        self.emp_b = DossierEmploye.objects.create(
            company=self.co_b, matricule='EMP-DOC-B', nom='Bennani', prenom='Z')

    def test_upload_creates_document_and_attachment(self):
        api = auth(self.user_a)
        resp = _upload(api, self.emp_a.id, date_expiration='2030-01-01')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = DocumentEmploye.objects.get(id=resp.data['id'])
        # Société posée côté serveur.
        self.assertEqual(doc.company, self.co_a)
        self.assertEqual(doc.employe, self.emp_a)
        self.assertEqual(doc.type_document, 'contrat')
        self.assertEqual(str(doc.date_expiration), '2030-01-01')
        # Pièce jointe records réutilisée (stockage MinIO mocké).
        self.assertIsNotNone(doc.attachment_id)
        att = Attachment.objects.get(id=doc.attachment_id)
        self.assertEqual(att.company, self.co_a)
        self.assertEqual(att.file_key, 'attachments/doc.pdf')
        # Métadonnées de fichier exposées en lecture + URL de téléchargement.
        self.assertEqual(resp.data['filename'], 'contrat.pdf')
        self.assertEqual(resp.data['mime'], 'application/pdf')
        self.assertIn(f'/{doc.attachment_id}/download/', resp.data['url'])

    def test_expiration_optional(self):
        api = auth(self.user_a)
        resp = _upload(api, self.emp_a.id, type_document='diplome')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = DocumentEmploye.objects.get(id=resp.data['id'])
        self.assertIsNone(doc.date_expiration)

    def test_upload_requires_file(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'employe': self.emp_a.id, 'type_document': 'cin'},
            format='multipart')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertNotIn(True, [DocumentEmploye.objects.exists()])

    def test_upload_rejects_foreign_employe(self):
        # emp_b appartient à la société B : refusé pour l'utilisateur A.
        api = auth(self.user_a)
        resp = _upload(api, self.emp_b.id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(DocumentEmploye.objects.exists())

    def test_list_filtered_by_employe_and_scoped(self):
        api = auth(self.user_a)
        self.assertEqual(_upload(api, self.emp_a.id).status_code, 201)
        emp_a2 = DossierEmploye.objects.create(
            company=self.co_a, matricule='EMP-DOC-A2', nom='C', prenom='D')
        self.assertEqual(_upload(api, emp_a2.id).status_code, 201)
        resp = api.get(f'{self.BASE}?employe={self.emp_a.id}')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['employe'], self.emp_a.id)

    def test_isolation_between_companies(self):
        api_a = auth(self.user_a)
        self.assertEqual(_upload(api_a, self.emp_a.id).status_code, 201)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refused(self):
        normal = make_user(self.co_a, 'rh-doc-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_delete_removes_attachment(self):
        api = auth(self.user_a)
        resp = _upload(api, self.emp_a.id)
        doc_id = resp.data['id']
        att_id = DocumentEmploye.objects.get(id=doc_id).attachment_id
        with mock.patch('apps.rh.views.delete_attachment') as del_mock:
            d = api.delete(f'{self.BASE}{doc_id}/')
        self.assertEqual(d.status_code, 204)
        self.assertFalse(DocumentEmploye.objects.filter(id=doc_id).exists())
        self.assertFalse(Attachment.objects.filter(id=att_id).exists())
        del_mock.assert_called_once()

    def test_expirant_bientot_endpoint(self):
        today = timezone.localdate()
        ct = self._make_attachment(self.co_a)
        # Expire dans 10 jours → dans la fenêtre.
        DocumentEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, attachment=ct,
            type_document='contrat', date_expiration=today + timedelta(days=10))
        # Sans échéance → exclu.
        DocumentEmploye.objects.create(
            company=self.co_a, employe=self.emp_a,
            attachment=self._make_attachment(self.co_a),
            type_document='diplome', date_expiration=None)
        # Déjà expiré → exclu.
        DocumentEmploye.objects.create(
            company=self.co_a, employe=self.emp_a,
            attachment=self._make_attachment(self.co_a),
            type_document='cin', date_expiration=today - timedelta(days=2))
        # Trop loin (90 j) → hors fenêtre de 30 j.
        DocumentEmploye.objects.create(
            company=self.co_a, employe=self.emp_a,
            attachment=self._make_attachment(self.co_a),
            type_document='rib', date_expiration=today + timedelta(days=90))

        resp = auth(self.user_a).get(f'{self.BASE}expirant-bientot/?within=30')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['type_document'], 'contrat')

    def test_selector_scopes_company(self):
        today = timezone.localdate()
        DocumentEmploye.objects.create(
            company=self.co_a, employe=self.emp_a,
            attachment=self._make_attachment(self.co_a),
            type_document='contrat', date_expiration=today + timedelta(days=5))
        # Société B ne voit rien via le sélecteur scopé.
        self.assertEqual(
            selectors.documents_expirant_bientot(self.co_b).count(), 0)
        self.assertEqual(
            selectors.documents_expirant_bientot(self.co_a).count(), 1)

    # -- helper -------------------------------------------------------------
    def _make_attachment(self, company):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(DossierEmploye)
        return Attachment.objects.create(
            company=company, content_type=ct, object_id=self.emp_a.id,
            file_key=f'attachments/{Attachment.objects.count()}.pdf',
            filename='f.pdf', size=1, mime='application/pdf')
