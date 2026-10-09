"""ENF7 — le contrat OpenAPI de la GED décrit ce que les vues font vraiment.

Couvre : identifiants non numériques et paramètres obligatoires/mal formés →
4xx nommé (jamais 500), doublons → 409, JSON seul hors envoi de fichier (D2),
et le schéma des vues GED/records se génère sans erreur.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged.models import Cabinet, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Enf7ContratGedTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='enf7-ged', defaults={'nom': 'ENF7 GED'})[0]
        self.admin = User.objects.create_user(
            username='enf7-ged-admin', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='C')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.api = auth(self.admin)

    def test_identifiants_non_numeriques_jamais_500(self):
        for route in ('archivages-legaux/', 'legal-holds/'):
            resp = self.api.post(
                f'{BASE}{route}', {'document': 'AAA'}, format='json')
            self.assertIn(resp.status_code, (400, 404), (route, resp.content))
        resp = self.api.post(
            f'{BASE}documents/scan-lot/', {'folder': 'AAA'},
            format='multipart')
        self.assertIn(resp.status_code, (400, 404), resp.content)
        resp = self.api.post(
            f'{BASE}documents/import-masse/', {'folder': 'AAA'},
            format='multipart')
        self.assertIn(resp.status_code, (400, 404), resp.content)

    def test_parametres_obligatoires_ou_mal_formes(self):
        resp = self.api.get(f'{BASE}demandes-document/checklist/')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(f'{BASE}annotations/export-annote/')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(
            f'{BASE}demandes-signature/tableau-bord/?emetteur=abc')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(
            f'{BASE}demandes-signature/tableau-bord/?date_debut=2026-13-45')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(f'{BASE}analytique/?date_fin=pas-une-date')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(f'{BASE}analytique/?date_debut=2026-01-01')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_doublon_armoire_409_et_json_seul(self):
        resp = self.api.post(f'{BASE}cabinets/', {'nom': 'C'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        # D2 : une vue sans fichier ne lit plus le multipart.
        resp = self.api.post(
            f'{BASE}roles-signataire/',
            {'nom': 'Client', 'peut_changer_signataire': '0'},
            format='multipart')
        self.assertEqual(resp.status_code, 415, resp.content)
        resp = self.api.post(
            f'{BASE}roles-signataire/',
            {'nom': 'Client', 'peut_changer_signataire': False},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_lien_vers_cible_introuvable_404(self):
        doc = self.api.post(f'{BASE}documents/', {
            'folder': self.folder.pk, 'nom': 'd.pdf'}, format='json')
        self.assertEqual(doc.status_code, 201, doc.content)
        resp = self.api.post(f'{BASE}liens/', {
            'document': doc.data['id'], 'model': 'crm.lead', 'id': 999999},
            format='json')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_schema_ged_et_records_se_genere(self):
        from drf_spectacular.generators import SchemaGenerator
        from django.urls import include, path

        from apps.ged import urls as ged_urls
        from apps.records import urls as records_urls

        generateur = SchemaGenerator(patterns=[
            path('api/django/ged/', include(ged_urls)),
            path('api/django/records/', include(records_urls)),
        ])
        schema = generateur.get_schema(request=None, public=True)
        chemins = schema['paths']
        self.assertIn('/api/django/ged/documents/{id}/tagger/', chemins)
        post = chemins['/api/django/ged/documents/{id}/tagger/']['post']
        self.assertIn('requestBody', post)
        liste = chemins['/api/django/ged/documents/']['get']
        noms = {p['name'] for p in liste['parameters']}
        self.assertTrue({'folder', 'coffre', 'tag', 'statut'} <= noms, noms)
