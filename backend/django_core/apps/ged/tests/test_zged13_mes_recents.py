"""ZGED13 — Section « Récents » de la GED (documents récemment
consultés/déposés).

Couvre :
  * consulter des documents les fait remonter dans `mes-recents/` dédupliqués
    et ordonnés ;
  * un collègue a ses propres récents ;
  * les documents en corbeille/hors ACL sont exclus ;
  * scoping société testé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder, JournalAcces

User = get_user_model()


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


class ZGed13Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged13-a', 'Zged13 A')
        self.admin_a = make_user(self.co_a, 'zged13-admin-a', 'admin')
        self.autre_a = make_user(self.co_a, 'zged13-autre-a', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc1 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc1.pdf')
        self.doc2 = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='doc2.pdf')


class ViewTests(ZGed13Base):
    def test_consulter_fait_remonter_dans_mes_recents_deduplique(self):
        JournalAcces.objects.create(
            company=self.co_a, document=self.doc1, utilisateur=self.admin_a,
            type_acces='consultation')
        JournalAcces.objects.create(
            company=self.co_a, document=self.doc2, utilisateur=self.admin_a,
            type_acces='consultation')
        # Deuxième accès à doc1 : ne doit pas dupliquer, doit remonter en tête.
        JournalAcces.objects.create(
            company=self.co_a, document=self.doc1, utilisateur=self.admin_a,
            type_acces='consultation')
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/mes-recents/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [d['id'] for d in resp.data['consultes']]
        self.assertEqual(ids[0], self.doc1.pk)
        self.assertEqual(len(ids), 2)  # dédupliqué

    def test_collegue_a_ses_propres_recents(self):
        JournalAcces.objects.create(
            company=self.co_a, document=self.doc1, utilisateur=self.admin_a,
            type_acces='consultation')
        api_autre = auth(self.autre_a)
        resp = api_autre.get('/api/django/ged/mes-recents/')
        self.assertEqual(resp.data['consultes'], [])

    def test_document_en_corbeille_exclu(self):
        JournalAcces.objects.create(
            company=self.co_a, document=self.doc1, utilisateur=self.admin_a,
            type_acces='consultation')
        from django.utils import timezone
        self.doc1.supprime_le = timezone.now()
        self.doc1.save()
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/mes-recents/')
        ids = [d['id'] for d in resp.data['consultes']]
        self.assertNotIn(self.doc1.pk, ids)

    def test_derniers_depots(self):
        DocumentVersion.objects.create(
            company=self.co_a, document=self.doc1, version=1,
            file_key='k1', uploaded_by=self.admin_a)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/mes-recents/')
        ids = [d['id'] for d in resp.data['deposes']]
        self.assertIn(self.doc1.pk, ids)

    def test_isolation_societe(self):
        co_b = make_company('zged13-b', 'Zged13 B')
        admin_b = make_user(co_b, 'zged13-admin-b', 'admin')
        JournalAcces.objects.create(
            company=self.co_a, document=self.doc1, utilisateur=self.admin_a,
            type_acces='consultation')
        api_b = auth(admin_b)
        resp = api_b.get('/api/django/ged/mes-recents/')
        self.assertEqual(resp.data['consultes'], [])
