"""T9 — import réutilisable : dry-run (aperçu/mapping) + commit (création seule,
doublons ignorés, multi-tenant)."""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


class ImportBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='imp-co', defaults={'nom': 'Imp Co'})[0]
        self.user = User.objects.create_user(
            username='imp_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _csv(self, content, name='data.csv'):
        return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/csv')


class TestDryRun(ImportBase):
    def test_dry_run_maps_and_lists_unmapped(self):
        f = self._csv('Nom,Email,Colonne Inconnue\nBennani,a@b.ma,xyz\n')
        resp = self.api.post('/api/django/imports/dry-run/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['mapping']['Nom'], 'nom')
        self.assertEqual(resp.data['mapping']['Email'], 'email')
        self.assertIn('Colonne Inconnue', resp.data['non_mappees'])
        self.assertEqual(resp.data['total_lignes'], 1)
        self.assertEqual(len(resp.data['apercu']), 1)


class TestCommit(ImportBase):
    def test_commit_creates_leads_and_skips_duplicates(self):
        Lead.objects.create(company=self.company, nom='Old', email='dup@x.ma')
        f = self._csv('Nom,Email,Telephone\n'
                      'Alaoui,new@x.ma,0600000000\n'
                      'Doublon,dup@x.ma,0611111111\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(len(resp.data['skipped']), 1)
        new = Lead.objects.get(email='new@x.ma')
        self.assertIn('Import', new.tags or '')  # origine marquée

    def test_commit_products_parses_price_and_skips_sku_dup(self):
        Produit.objects.create(company=self.company, nom='Existant', sku='SKU-1',
                               prix_vente=10)
        f = self._csv('Nom,SKU,Prix,Quantite\n'
                      'Panneau,SKU-9,"1 200,50",12\n'
                      'Doublon,SKU-1,500,3\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'products'}, format='multipart')
        self.assertEqual(resp.data['created'], 1)
        p = Produit.objects.get(sku='SKU-9')
        self.assertEqual(str(p.prix_vente), '1200.50')

    def test_commit_clients(self):
        f = self._csv('Nom,Email\nSociété A,a@a.ma\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'clients'}, format='multipart')
        self.assertEqual(resp.data['created'], 1)
        self.assertTrue(Client.objects.filter(company=self.company, nom='Société A').exists())


class TestGenericExport(ImportBase):
    def test_export_devis_xlsx(self):
        c = Client.objects.create(company=self.company, nom='C')
        from decimal import Decimal
        from apps.ventes.models import Devis
        Devis.objects.create(company=self.company, reference='DEV-EXP-1', client=c,
                             taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        resp = self.api.post('/api/django/imports/export/devis/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_unknown_entity_400(self):
        resp = self.api.post('/api/django/imports/export/bogus/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
