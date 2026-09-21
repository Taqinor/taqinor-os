"""Tests XKB17 — Export/import & sauvegarde KB.

Couvre :
* export PDF fidèle d'un article (contenu PDF, statut inchangé) ;
* export Markdown fidèle d'un article (titre + corps) ;
* import Markdown crée un nouvel article brouillon ;
* export ZIP contient tous les articles de la société et RIEN d'une autre.
"""
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import services
from apps.kb.models import KbArticle

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


class KbExportImportServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-exp', 'E')
        self.user = make_user(self.co, 'kb-exp-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Procédure X', corps='Contenu Y',
            categorie='SOP', tags='urgent', statut=KbArticle.Statut.PUBLIE)

    def test_article_to_markdown_contains_title_and_body(self):
        md = services.article_to_markdown(self.article)
        self.assertIn('# Procédure X', md)
        self.assertIn('Contenu Y', md)
        self.assertIn('SOP', md)

    def test_article_to_pdf_returns_pdf_bytes(self):
        pdf_bytes = services.article_to_pdf(self.article)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        # Aucun statut touché par l'export.
        self.article.refresh_from_db()
        self.assertEqual(self.article.statut, KbArticle.Statut.PUBLIE)

    def test_importer_markdown_creates_draft_article(self):
        contenu = '# Mon titre importé\n\nCorps du texte.'
        article = services.importer_markdown(
            contenu, company=self.co, auteur=self.user)
        self.assertEqual(article.titre, 'Mon titre importé')
        self.assertEqual(article.corps, contenu)
        self.assertEqual(article.corps_format, KbArticle.CorpsFormat.MARKDOWN)
        self.assertEqual(article.statut, KbArticle.Statut.BROUILLON)
        self.assertEqual(article.company, self.co)

    def test_importer_markdown_without_title_uses_fallback(self):
        article = services.importer_markdown(
            'Pas de titre ATX ici.', company=self.co)
        self.assertEqual(article.titre, 'Article importé')

    def test_exporter_zip_scoped_to_company(self):
        other_co = make_company('kb-exp-other', 'O')
        KbArticle.objects.create(
            company=other_co, titre='Autre société', corps='secret')
        zip_bytes = services.exporter_zip_company(self.co)
        zf = zipfile.ZipFile(BytesIO(zip_bytes))
        names = zf.namelist()
        self.assertTrue(
            any('Procédure' in n or str(self.article.id) in n for n in names))
        self.assertFalse(
            any('Autre-societe' in n or 'Autre société' in n for n in names))
        content = zf.read(names[0]).decode('utf-8')
        self.assertNotIn('secret', content)


class KbExportImportApiTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-exp-api', 'A')
        self.user = make_user(self.co, 'kb-exp-api-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Fiche API', corps='Détails')

    def test_export_pdf_endpoint(self):
        resp = auth(self.user).get(
            f'{self.ARTICLES}{self.article.id}/export-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_export_markdown_endpoint(self):
        resp = auth(self.user).get(
            f'{self.ARTICLES}{self.article.id}/export-markdown/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Fiche API', resp.content)

    def test_import_markdown_endpoint(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}importer-markdown/',
            {'contenu': '# Importé via API\n\nTexte.'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['titre'], 'Importé via API')
        self.assertTrue(
            KbArticle.objects.filter(
                company=self.co, titre='Importé via API').exists())

    def test_import_markdown_endpoint_requires_content(self):
        resp = auth(self.user).post(
            f'{self.ARTICLES}importer-markdown/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_export_zip_endpoint(self):
        resp = auth(self.user).get(f'{self.ARTICLES}export-zip/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        zf = zipfile.ZipFile(BytesIO(resp.content))
        self.assertTrue(len(zf.namelist()) >= 1)
