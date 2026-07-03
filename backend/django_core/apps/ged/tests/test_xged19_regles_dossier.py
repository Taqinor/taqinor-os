"""XGED19 — Actions automatiques par dossier (règles à l'upload).

Couvre :
  * une règle « PDF contenant "facture" → tag Compta » s'applique à l'upload ;
  * l'échec d'une action est journalisé sans bloquer l'upload ;
  * conditions (core.rules), actions, isolation par société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, DocumentTag, ExecutionRegleDossier, Folder,
    RegleDossier,
)

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


class XGed19Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged19-a', 'Xged19 A')
        self.admin_a = make_user(self.co_a, 'xged19-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Entrant')
        self.tag_compta = DocumentTag.objects.create(
            company=self.co_a, nom='Compta', slug='compta')


class AppliquerReglesTests(XGed19Base):
    def test_regle_tag_facture_applique_au_upload(self):
        RegleDossier.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Facture → Compta',
            condition_group={
                'op': 'and', 'conditions': [
                    {'field': 'nom', 'operator': 'contains', 'value': 'facture'},
                ],
            },
            actions=[{'type': 'tag', 'params': {'tag': 'compta'}}])
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='facture-042.pdf')
        executions = services.appliquer_regles_dossier(doc, user=self.admin_a)
        self.assertEqual(len(executions), 1)
        self.assertTrue(executions[0].declenchee)
        self.assertTrue(doc.tag_assignments.filter(tag=self.tag_compta).exists())

    def test_regle_non_declenchee_sans_match(self):
        RegleDossier.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Facture → Compta',
            condition_group={
                'op': 'and', 'conditions': [
                    {'field': 'nom', 'operator': 'contains', 'value': 'facture'},
                ],
            },
            actions=[{'type': 'tag', 'params': {'tag': 'compta'}}])
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='bon-livraison.pdf')
        executions = services.appliquer_regles_dossier(doc, user=self.admin_a)
        self.assertFalse(executions[0].declenchee)
        self.assertFalse(doc.tag_assignments.filter(tag=self.tag_compta).exists())

    def test_action_en_echec_journalisee_sans_bloquer(self):
        RegleDossier.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Tag inconnu',
            condition_group={'field': 'nom', 'operator': 'contains', 'value': 'x'},
            actions=[{'type': 'tag', 'params': {'tag': 'inconnu-slug'}}])
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='x-doc.pdf')
        # Ne doit JAMAIS lever, même si l'action échoue.
        executions = services.appliquer_regles_dossier(doc, user=self.admin_a)
        self.assertTrue(executions[0].declenchee)
        self.assertFalse(executions[0].resultats[0]['ok'])

    def test_inactive_rule_not_applied(self):
        RegleDossier.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Désactivée',
            condition_group={'field': 'nom', 'operator': 'contains', 'value': 'x'},
            actions=[{'type': 'tag', 'params': {'tag': 'compta'}}],
            actif=False)
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='x-doc.pdf')
        executions = services.appliquer_regles_dossier(doc, user=self.admin_a)
        self.assertEqual(executions, [])

    def test_upload_endpoint_applies_rule(self):
        RegleDossier.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Facture → Compta',
            condition_group={'field': 'nom', 'operator': 'contains',
                             'value': 'facture'},
            actions=[{'type': 'tag', 'params': {'tag': 'compta'}}])
        api = auth(self.admin_a)
        pdf_bytes = b'%PDF-1.4\n%test\n%%EOF'
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile(
            'facture-99.pdf', pdf_bytes, content_type='application/pdf')
        resp = api.post('/api/django/ged/documents/televerser/', {
            'folder': self.folder_a.pk, 'file': upload,
        }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = Document.objects.get(pk=resp.data['id'])
        self.assertTrue(doc.tag_assignments.filter(tag=self.tag_compta).exists())
        self.assertTrue(
            ExecutionRegleDossier.objects.filter(document=doc).exists())
