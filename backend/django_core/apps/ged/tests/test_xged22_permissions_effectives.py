"""XGED22 — Rapport de permissions effectives (« qui voit ce document et
pourquoi »).

Couvre :
  * le rapport liste chaque principal avec son niveau et sa source ;
  * l'export CSV fonctionne ;
  * un non-gestionnaire → 403 ;
  * idem au niveau dossier.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors
from apps.ged.models import AclGed, Cabinet, Document, Folder
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_role(company, nom):
    return Role.objects.create(company=company, nom=nom)


def make_user(company, username, role=None, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XGed22Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged22-a', 'Xged22 A')
        self.role_rh = make_role(self.co_a, 'RH')
        self.admin_a = make_user(
            self.co_a, 'xged22-admin-a', role=None, role_legacy='admin')
        self.user_rh = make_user(self.co_a, 'xged22-rh', role=self.role_rh)
        self.user_autre = make_user(self.co_a, 'xged22-autre')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='RH')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='bulletin.pdf')


class SelectorTests(XGed22Base):
    def test_rapport_liste_chaque_principal_avec_source(self):
        AclGed.objects.create(
            company=self.co_a, document=self.doc, role=self.role_rh,
            niveau='lecture', herite=False)
        lignes = selectors.permissions_effectives(self.doc)
        by_id = {ligne['id']: ligne for ligne in lignes}
        self.assertEqual(by_id[self.admin_a.pk]['source'], 'admin')
        self.assertEqual(by_id[self.admin_a.pk]['niveau'], 'gestion')
        self.assertEqual(by_id[self.user_rh.pk]['source'], 'override_document')
        self.assertEqual(by_id[self.user_rh.pk]['niveau'], 'lecture')
        self.assertEqual(by_id[self.user_autre.pk]['source'], 'aucune')
        self.assertIsNone(by_id[self.user_autre.pk]['niveau'])

    def test_heritage_dossier_justifie(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.folder_a, role=self.role_rh,
            niveau='ecriture', herite=True)
        lignes = selectors.permissions_effectives(self.doc)
        by_id = {ligne['id']: ligne for ligne in lignes}
        self.assertEqual(by_id[self.user_rh.pk]['source'], 'heritage_dossier')
        self.assertEqual(by_id[self.user_rh.pk]['niveau'], 'ecriture')

    def test_folder_report(self):
        AclGed.objects.create(
            company=self.co_a, folder=self.folder_a, role=self.role_rh,
            niveau='lecture', herite=False)
        lignes = selectors.permissions_effectives(self.folder_a)
        by_id = {ligne['id']: ligne for ligne in lignes}
        self.assertEqual(by_id[self.user_rh.pk]['source'], 'override_dossier')


class ViewTests(XGed22Base):
    def test_endpoint_document_liste_et_403_non_gestionnaire(self):
        AclGed.objects.create(
            company=self.co_a, document=self.doc, role=self.role_rh,
            niveau='lecture', herite=False)
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc.pk}/permissions-effectives/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(len(resp.data['lignes']) >= 3)

        api_autre = auth(self.user_autre)
        resp2 = api_autre.get(
            f'/api/django/ged/documents/{self.doc.pk}/permissions-effectives/')
        self.assertEqual(resp2.status_code, 403)

    def test_export_csv(self):
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/documents/{self.doc.pk}/permissions-effectives/'
            '?format=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        content = resp.content.decode('utf-8')
        self.assertIn('type,principal,niveau,source', content)
        self.assertIn(self.admin_a.username, content)

    def test_endpoint_dossier(self):
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/dossiers/{self.folder_a.pk}/permissions-effectives/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(len(resp.data['lignes']) >= 3)

    def test_isolation_societe(self):
        co_b = make_company('xged22-b', 'Xged22 B')
        user_b = make_user(co_b, 'xged22-user-b', role_legacy='admin')
        api_b = auth(user_b)
        resp = api_b.get(
            f'/api/django/ged/documents/{self.doc.pk}/permissions-effectives/')
        self.assertEqual(resp.status_code, 404)
