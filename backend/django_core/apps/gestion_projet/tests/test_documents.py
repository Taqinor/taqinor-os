"""Tests des documents & plans versionnés (PROJ33).

Un ``DocumentProjet`` porte N ``VersionDocument`` ; le numéro de version et
l'auteur sont posés CÔTÉ SERVEUR au dépôt (jamais du corps) — les versions ne
s'écrasent jamais. Couvre : dépôt incrémental (v1, v2…) ; cache
``derniere_version`` ; auteur posé serveur ; dépôt sans fichier → 400 ; service
de dépôt atomique ; scoping (404 cross-tenant) ; accès Administrateur/
Responsable (403 pour ``normal``).
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import DocumentProjet, Projet

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


def _fichier(nom='plan.pdf', contenu=b'data'):
    return SimpleUploadedFile(nom, contenu, content_type='application/pdf')


class DocumentServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-doc-svc', 'S')
        self.user = make_user(self.co, 'doc-svc')
        self.projet = Projet.objects.create(
            company=self.co, code='P-DOC', nom='P')
        self.document = DocumentProjet.objects.create(
            company=self.co, projet=self.projet, nom='Plan toiture')

    def test_deposer_incremente_version(self):
        v1 = services.deposer_version_document(
            self.document, _fichier(), auteur=self.user)
        v2 = services.deposer_version_document(
            self.document, _fichier('plan2.pdf'), auteur=self.user)
        self.assertEqual(v1.version, 1)
        self.assertEqual(v2.version, 2)
        self.document.refresh_from_db()
        self.assertEqual(self.document.derniere_version, 2)
        self.assertEqual(v1.company_id, self.co.id)
        self.assertEqual(v2.auteur_id, self.user.id)


class DocumentApiTests(TestCase):
    BASE = '/api/django/gestion-projet/documents/'

    def setUp(self):
        self.co_a = make_company('gp-doc-a', 'A')
        self.co_b = make_company('gp-doc-b', 'B')
        self.user_a = make_user(self.co_a, 'doc-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_creation_et_depot(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'nom': 'Plan', 'type_doc': 'plan',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc_id = resp.data['id']
        self.assertEqual(resp.data['derniere_version'], 0)

        # Dépôt d'une révision (multipart).
        resp2 = api.post(
            f'{self.BASE}{doc_id}/deposer/',
            {'fichier': _fichier(), 'commentaire': 'init'},
            format='multipart')
        self.assertEqual(resp2.status_code, 201, resp2.data)
        self.assertEqual(resp2.data['version'], 1)
        self.assertEqual(resp2.data['auteur'], self.user_a.id)

        doc = DocumentProjet.objects.get(id=doc_id)
        self.assertEqual(doc.derniere_version, 1)

    def test_depot_sans_fichier_400(self):
        doc = DocumentProjet.objects.create(
            company=self.co_a, projet=self.projet, nom='D')
        api = auth(self.user_a)
        resp = api.post(f'{self.BASE}{doc.id}/deposer/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_versions_endpoint(self):
        doc = DocumentProjet.objects.create(
            company=self.co_a, projet=self.projet, nom='D')
        services.deposer_version_document(
            doc, _fichier(), auteur=self.user_a)
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{doc.id}/versions/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_cross_tenant_404(self):
        autre_p = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        autre_d = DocumentProjet.objects.create(
            company=self.co_b, projet=autre_p, nom='D')
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}{autre_d.id}/deposer/',
            {'fichier': _fichier()}, format='multipart')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'doc-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
