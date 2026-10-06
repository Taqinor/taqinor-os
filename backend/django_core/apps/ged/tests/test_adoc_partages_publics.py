"""ADOC6 — les liens publics GED respectent l'ACL et la corbeille.

Rejoue les sondes #41/#49 de l'audit documents (2026-10-05) : un employé
« normal » lisait le jeton d'un partage d'un document du coffre d'autrui ; un
responsable partageait un document qu'il ne voit pas (201) ; un PATCH
réactivait un lien révoqué ; un document en corbeille restait servi (200).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    Cabinet, Coffre, Document, DocumentVersion, Folder, PartageGed,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'
PDF = b'%PDF-1.4\n%%EOF'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def lignes(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class PartagesPublicsTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc6', defaults={'nom': 'ADOC6'})[0]
        self.admin = User.objects.create_user(
            username='adoc6-admin', password='x', company=self.co,
            role_legacy='admin')
        self.emp1 = User.objects.create_user(
            username='adoc6-emp1', password='x', company=self.co,
            role_legacy='normal')
        self.emp2 = User.objects.create_user(
            username='adoc6-emp2', password='x', company=self.co,
            role_legacy='normal')
        self.resp = User.objects.create_user(
            username='adoc6-resp', password='x', company=self.co,
            role_legacy='responsable')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        coffre = Coffre.objects.create(
            company=self.co, nom='Coffre emp1', proprietaire=self.emp1)
        self.doc_secret = Document.objects.create(
            company=self.co, folder=folder, coffre=coffre, nom='Secret')
        self.partage_secret = services.create_partage(
            document=self.doc_secret, company=self.co, created_by=self.admin)
        self.doc_public = Document.objects.create(
            company=self.co, folder=folder, nom='Public')
        DocumentVersion.objects.create(
            company=self.co, document=self.doc_public, version=1,
            file_key='attachments/p.pdf', filename='p.pdf', size=len(PDF),
            mime='application/pdf')
        self.partage_public = services.create_partage(
            document=self.doc_public, company=self.co, created_by=self.admin)

    def test_jeton_masque(self):
        resp = auth(self.emp2).get(f'{BASE}partages/')
        self.assertEqual(resp.status_code, 200)
        rows = lignes(resp)
        ids = [r['id'] for r in rows]
        self.assertNotIn(self.partage_secret.pk, ids)
        self.assertNotIn(self.partage_secret.token, str(resp.content))
        ligne = next(r for r in rows if r['id'] == self.partage_public.pk)
        self.assertNotIn('token', ligne)
        self.assertNotIn('public_url', ligne)
        # Le créateur (admin) voit toujours le jeton.
        resp = auth(self.admin).get(f'{BASE}partages/')
        ligne = next(r for r in lignes(resp) if r['id'] == self.partage_public.pk)
        self.assertEqual(ligne['token'], self.partage_public.token)

    def test_creation_doc_invisible_400(self):
        api = auth(self.resp)
        self.assertEqual(
            api.get(f'{BASE}documents/{self.doc_secret.pk}/').status_code, 404)
        avant = PartageGed.objects.count()
        resp = api.post(f'{BASE}partages/', {'document': self.doc_secret.pk},
                        format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        absent = api.post(f'{BASE}partages/', {'document': 999999},
                          format='json')
        self.assertEqual(
            [str(m).replace(str(self.doc_secret.pk), '{pk}')
             for m in resp.data['document']],
            [str(m).replace('999999', '{pk}') for m in absent.data['document']])
        self.assertEqual(PartageGed.objects.count(), avant)

    def test_reactivation_patch_ignoree(self):
        services.revoke_partage(self.partage_public)
        resp = auth(self.admin).patch(
            f'{BASE}partages/{self.partage_public.pk}/', {'actif': True},
            format='json')
        self.assertIn(resp.status_code, (200, 400), resp.content)
        self.partage_public.refresh_from_db()
        self.assertFalse(self.partage_public.actif)

    def test_corbeille_404(self):
        url = f'{BASE}public/{self.partage_public.token}/'
        with mock.patch('apps.ged.views.fetch_attachment',
                        return_value=(PDF, None)):
            avant = APIClient().get(url)
            self.assertNotEqual(avant.status_code, 404)
            services.mettre_en_corbeille(self.doc_public, self.admin)
            apres = APIClient().get(url)
        self.assertEqual(apres.status_code, 404)
        statut, _ = services.resolve_partage_public(self.partage_public.token)
        self.assertEqual(statut, services.PARTAGE_INTROUVABLE)
