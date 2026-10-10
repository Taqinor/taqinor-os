"""ADOC22 — les exceptions métier GED sortent en 4xx nommés, jamais en 500.

Constats #24, #25, #26, #50, #53 de l'audit documents (2026-10-05) : doublon
d'armoire / de tampon, document archivé sur assigner/verrouiller, fusion de
PNG, disposition bloquée par un document archivé, archivage d'un document en
corbeille — tous répondaient 500.
"""
import io
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import (
    ArchivageLegal, Cabinet, DemandeDisposition, Document, Folder,
    PolitiqueRetention, TamponSociete,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), 'white').save(buf, format='PNG')
    return buf.getvalue()


class ErreursMetierTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc22', defaults={'nom': 'ADOC22'})[0]
        self.admin = User.objects.create_user(
            username='adoc22-admin', password='x', company=self.co,
            role_legacy='admin')
        self.admin2 = User.objects.create_user(
            username='adoc22-admin2', password='x', company=self.co,
            role_legacy='admin')
        self.cab = Cabinet.objects.create(company=self.co, nom='X')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='R')
        self.api = auth(self.admin)

    def _archiver(self, doc):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'abc', None)):
            return services.archiver_legalement(doc, user=self.admin)

    def test_doublon_armoire_409(self):
        # ENF7 — le doublon (société, nom) est refusé par la garde d'unicité
        # plateforme (409 `unique_conflict`), plus par un 400 maison.
        resp = self.api.post(f'{BASE}cabinets/', {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(resp.data['error']['code'], 'unique_conflict')
        self.assertEqual(Cabinet.objects.filter(nom='X').count(), 1)

    def test_doublon_tampon_409(self):
        TamponSociete.objects.create(company=self.co, libelle='Y')
        resp = self.api.post(f'{BASE}tampons-societe/', {'libelle': 'Y'},
                             format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(resp.data['error']['code'], 'unique_conflict')
        self.assertEqual(TamponSociete.objects.filter(libelle='Y').count(), 1)

    def test_assigner_archive_403(self):
        doc = Document.objects.create(company=self.co, folder=self.folder,
                                      nom='archive.pdf')
        self._archiver(doc)
        for route, corps in (('assigner', {'proprietaire': self.admin.pk}),
                             ('verrouiller', {}), ('deverrouiller', {})):
            resp = self.api.post(f'{BASE}documents/{doc.pk}/{route}/', corps,
                                 format='json')
            self.assertEqual(resp.status_code, 403, (route, resp.content))
        doc.refresh_from_db()
        self.assertIsNone(doc.proprietaire_id)

    def test_fusion_png_400(self):
        octets = _png()
        docs = []
        for nom in ('a.png', 'b.png'):
            d = Document.objects.create(company=self.co, folder=self.folder,
                                        nom=nom)
            services.add_version(d, file_key=f'attachments/{nom}',
                                 company=self.co, mime='image/png')
            docs.append(d)
        avant = Document.objects.count()
        with mock.patch('apps.ged.services._fetch_version_bytes',
                        return_value=(octets, None)):
            resp = self.api.post(f'{BASE}documents/fusionner/', {
                'documents': [d.pk for d in docs]}, format='json')
            self.assertEqual(resp.status_code, 400, resp.content)
            self.assertIn('réservée aux PDF', resp.data['detail'])
            resp = self.api.post(f'{BASE}documents/{docs[0].pk}/scinder/',
                                 {'points_de_coupe': [1]}, format='json')
            self.assertEqual(resp.status_code, 400, resp.content)
            resp = self.api.post(f'{BASE}documents/{docs[0].pk}/caviarder/', {
                'zones': [{'page': 0, 'x0': 0, 'y0': 0, 'x1': 10,
                           'y1': 10}]}, format='json')
            self.assertEqual(resp.status_code, 400, resp.content)
            version = docs[0].versions.first()
            resp = self.api.get(
                f'{BASE}annotations/export-annote/?version={version.pk}')
            self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(Document.objects.count(), avant)

    def test_disposition_ignore_archive(self):
        PolitiqueRetention.objects.create(
            company=self.co, nom='Globale', duree_conservation_jours=30)
        vieux = Document.objects.create(company=self.co, folder=self.folder,
                                        nom='vieux.pdf')
        archive = Document.objects.create(company=self.co, folder=self.folder,
                                          nom='archive.pdf')
        Document.objects.filter(pk__in=[vieux.pk, archive.pk]).update(
            created_at=timezone.now() - timedelta(days=400))
        demande = services.creer_demande_disposition(
            self.co, libelle='Purge', document_ids=[vieux.pk, archive.pk],
            user=self.admin)
        services.approuver_demande_disposition(demande, user=self.admin2)
        self._archiver(archive)
        resp = auth(self.admin2).post(
            f'{BASE}demandes-disposition/{demande.pk}/executer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'executee')
        self.assertIn('1 document(s) ignoré(s)', demande.commentaire)
        self.assertFalse(Document.objects.filter(pk=vieux.pk).exists())
        self.assertTrue(Document.objects.filter(pk=archive.pk).exists())
        self.assertTrue(ArchivageLegal.objects.filter(document=archive).exists())
        self.assertEqual(DemandeDisposition.objects.count(), 1)

    def test_archiver_corbeille_400(self):
        doc = Document.objects.create(company=self.co, folder=self.folder,
                                      nom='jete.pdf')
        services.mettre_en_corbeille(doc, self.admin)
        resp = self.api.post(f'{BASE}archivages-legaux/',
                             {'document': doc.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(ArchivageLegal.objects.filter(document=doc).exists())


# ENF7 — le contrat OpenAPI de la GED décrit ce que les vues font vraiment. Couvre : identifiants
# non numériques et paramètres obligatoires/mal formés → 4xx nommé (jamais 500), doublons → 409,
# JSON seul hors envoi de fichier (D2), et le schéma des vues GED/records se génère sans erreur.
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
