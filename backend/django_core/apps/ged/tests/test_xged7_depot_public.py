"""XGED7 — Lien public de DÉPÔT (upload-request).

Couvre :
  * un visiteur dépose un fichier via le lien public → apparaît dans le bon
    dossier, sans visibilité sur le contenu existant (isolation) ;
  * lien expiré/quota épuisé → 410 ;
  * jeton inconnu/révoqué → 404 ;
  * scoping société de la gestion (DepotPublicViewSet).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, DepotPublic, Folder

User = get_user_model()

_PDF_BYTES = (
    b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XGed7Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged7-a', 'Xged7 A')
        self.admin_a = make_user(self.co_a, 'xged7-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Pièces clients')
        # Document PRÉEXISTANT — ne doit jamais être visible via le dépôt public.
        self.doc_existant = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Secret interne')


class ServiceDepositTests(XGed7Base):
    def test_deposer_via_lien_public_creates_document(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a, created_by=self.admin_a)
        doc = services.deposer_via_lien_public(
            depot, file_key='attachments/x.pdf', filename='cin.pdf',
            size=1234, mime='application/pdf',
            uploader_nom='Karim', uploader_email='karim@x.com')
        self.assertEqual(doc.folder_id, self.folder_a.pk)
        self.assertEqual(doc.custom_data['uploader_nom'], 'Karim')
        depot.refresh_from_db()
        self.assertEqual(depot.depots_effectues, 1)
        self.assertEqual(depot.octets_deposes, 1234)

    def test_quota_fichiers_exhausted_rejects(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a, quota_fichiers=1)
        services.deposer_via_lien_public(
            depot, file_key='a.pdf', filename='a.pdf', size=10,
            mime='application/pdf')
        depot.refresh_from_db()
        with self.assertRaises(ValueError):
            services.deposer_via_lien_public(
                depot, file_key='b.pdf', filename='b.pdf', size=10,
                mime='application/pdf')

    def test_resolve_expired_returns_expire(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a,
            expires_at=timezone.now() - timedelta(days=1))
        statut, resolved = services.resolve_depot_public(depot.token)
        self.assertEqual(statut, services.DEPOT_EXPIRE)
        self.assertIsNone(resolved)

    def test_resolve_unknown_token_returns_introuvable(self):
        statut, resolved = services.resolve_depot_public('does-not-exist')
        self.assertEqual(statut, services.DEPOT_INTROUVABLE)
        self.assertIsNone(resolved)

    def test_revoked_link_is_introuvable(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a)
        services.revoke_depot_public(depot)
        statut, _ = services.resolve_depot_public(depot.token)
        self.assertEqual(statut, services.DEPOT_INTROUVABLE)


class PublicEndpointTests(XGed7Base):
    def test_get_returns_message_without_leaking_existing_documents(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a, message='Merci de déposer votre CIN')
        api = APIClient()
        resp = api.get(f'/api/django/ged/depot/{depot.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['message'], 'Merci de déposer votre CIN')
        self.assertNotIn('documents', resp.data)

    def test_post_deposits_file(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a)
        api = APIClient()
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile('x.pdf', _PDF_BYTES, content_type='application/pdf')
        resp = api.post(
            f'/api/django/ged/depot/{depot.token}/',
            {'file': upload, 'nom': 'Visiteur', 'email': 'v@x.com'},
            format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            Document.objects.filter(pk=resp.data['document']).exists())

    def test_unknown_token_404(self):
        api = APIClient()
        resp = api.get('/api/django/ged/depot/unknown-token/')
        self.assertEqual(resp.status_code, 404)

    def test_expired_link_410(self):
        depot = services.create_depot_public(
            folder=self.folder_a, company=self.co_a,
            expires_at=timezone.now() - timedelta(days=1))
        api = APIClient()
        resp = api.get(f'/api/django/ged/depot/{depot.token}/')
        self.assertEqual(resp.status_code, 410)


class GestionViewsetTests(XGed7Base):
    def test_create_and_revoke(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/depots-publics/', {
            'folder': self.folder_a.pk, 'message': 'Envoyez vos pièces',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        depot_id = resp.data['id']
        self.assertTrue(DepotPublic.objects.filter(
            pk=depot_id, company=self.co_a, created_by=self.admin_a).exists())
        resp2 = api.post(f'/api/django/ged/depots-publics/{depot_id}/revoquer/')
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.data['actif'])
