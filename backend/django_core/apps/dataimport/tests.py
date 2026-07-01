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
        from apps.roles.models import Role, DIRECTEUR_PERMISSIONS
        self.company = Company.objects.get_or_create(
            slug='imp-co', defaults={'nom': 'Imp Co'})[0]
        self.user = User.objects.create_user(
            username='imp_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        # QG4 — l'import de PRODUITS est réservé aux rôles Directeur +
        # Commercial responsable : les tests produits passent par un Directeur,
        # les autres cibles restent sur le responsable hérité (non-régression).
        role_dir = Role.objects.get_or_create(
            company=self.company, nom='Directeur',
            defaults={'permissions': list(DIRECTEUR_PERMISSIONS),
                      'est_systeme': True})[0]
        self.directeur = User.objects.create_user(
            username='imp_dir', password='x', role=role_dir,
            company=self.company)
        self.api_dir = APIClient()
        self.api_dir.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.directeur)}')

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
        resp = self.api_dir.post(
            '/api/django/imports/commit/',
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


class TestCommitHardening(ImportBase):
    def test_product_opening_stock_creates_audit_movement(self):
        # ERR52 — un stock d'ouverture > 0 passe par MouvementStock (audit).
        from apps.stock.models import MouvementStock
        f = self._csv('Nom,SKU,Quantite\nPanneau,SKU-AUD,5\n')
        resp = self.api_dir.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'products'}, format='multipart')
        self.assertEqual(resp.data['created'], 1)
        p = Produit.objects.get(sku='SKU-AUD')
        self.assertEqual(p.quantite_stock, 5)
        mvt = MouvementStock.objects.get(produit=p)
        self.assertEqual(mvt.type_mouvement,
                         MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(mvt.quantite, 5)
        self.assertEqual(mvt.quantite_avant, 0)
        self.assertEqual(mvt.quantite_apres, 5)
        self.assertEqual(mvt.company, self.company)

    def test_negative_opening_stock_is_refused(self):
        # ERR52 — un stock négatif est ignoré (pas de produit, pas de mouvement).
        from apps.stock.models import MouvementStock
        f = self._csv('Nom,SKU,Quantite\nNeg,SKU-NEG,-3\n')
        resp = self.api_dir.post(
            '/api/django/imports/commit/',
            {'file': f, 'target': 'products'}, format='multipart')
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertFalse(Produit.objects.filter(sku='SKU-NEG').exists())
        self.assertEqual(MouvementStock.objects.count(), 0)

    def test_commit_is_atomic_on_midloop_error(self):
        # ERR51 — si une ligne plante en cours de boucle, AUCUNE ligne n'est
        # créée (l'import est tout-ou-rien).
        from unittest import mock
        f = self._csv('Nom,Email\nA,a@x.ma\nB,b@x.ma\n')
        before = Lead.objects.filter(company=self.company).count()
        real_create = Lead.objects.create

        def boom(*args, **kwargs):
            if kwargs.get('nom') == 'B':
                raise RuntimeError('boom')
            return real_create(*args, **kwargs)

        with mock.patch.object(Lead.objects, 'create', side_effect=boom):
            resp = self.api.post('/api/django/imports/commit/',
                                 {'file': f, 'target': 'leads'},
                                 format='multipart')
        self.assertEqual(resp.status_code, 400)
        # Rollback complet : la 1re ligne (A) n'a PAS survécu.
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), before)

    def test_row_cap_rejected_with_clear_400(self):
        # ERR53 — un fichier au-delà du plafond de lignes → 400 explicite.
        from . import services
        rows = '\n'.join(f'L{i},l{i}@x.ma' for i in range(services.MAX_ROWS + 1))
        f = self._csv('Nom,Email\n' + rows + '\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('lignes', resp.data['detail'].lower())

    def test_oversized_upload_rejected(self):
        # ERR53 — un upload trop volumineux (octets) → 400 avant tout parsing.
        from .views import MAX_UPLOAD_BYTES
        big = 'Nom,Email\n' + ('x' * (MAX_UPLOAD_BYTES + 10))
        f = self._csv(big)
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'leads'}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('volumineux', resp.data['detail'].lower())


class TestFournisseursImport(ImportBase):
    """FG14 — import de fournisseurs."""

    def test_creates_fournisseur(self):
        from apps.stock.models import Fournisseur
        f = self._csv('Nom,Email,Telephone\nFournisseur A,fa@x.ma,0600000001\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'fournisseurs'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertTrue(
            Fournisseur.objects.filter(company=self.company, nom='Fournisseur A').exists())

    def test_skips_duplicate_nom(self):
        from apps.stock.models import Fournisseur
        Fournisseur.objects.create(company=self.company, nom='Dup Four')
        f = self._csv('Nom\nDup Four\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'fournisseurs'}, format='multipart')
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(len(resp.data['skipped']), 1)

    def test_skips_missing_nom(self):
        f = self._csv('Email\nsome@x.ma\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'fournisseurs'}, format='multipart')
        self.assertEqual(resp.data['created'], 0)


class TestEquipementsImport(ImportBase):
    """FG14 — import d'équipements (résolution produit/installation)."""

    def setUp(self):
        super().setUp()
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.installations.models import Installation
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Test', sku='SKU-EQ1', prix_vente=0)
        self.client_inst = Client.objects.create(
            company=self.company, nom='Client EQ')
        self.installation = Installation.objects.create(
            company=self.company, reference='CHANT-EQ1',
            client=self.client_inst,
        )

    def test_creates_equipement(self):
        from apps.sav.models import Equipement
        f = self._csv(
            'SKU,Chantier,Serie\n'
            'SKU-EQ1,CHANT-EQ1,SN-001\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'equipements'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertTrue(
            Equipement.objects.filter(
                company=self.company, numero_serie='SN-001').exists())

    def test_skips_unknown_sku(self):
        f = self._csv('SKU,Chantier\nSKU-UNKNOWN,CHANT-EQ1\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'equipements'}, format='multipart')
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertIn('produit SKU inconnu', resp.data['skipped'][0]['raison'])

    def test_skips_unknown_installation(self):
        f = self._csv('SKU,Chantier\nSKU-EQ1,CHANT-BOGUS\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'equipements'}, format='multipart')
        self.assertEqual(resp.data['created'], 0)
        self.assertIn('installation inconnue', resp.data['skipped'][0]['raison'])

    def test_skips_missing_produit_sku(self):
        f = self._csv('Chantier\nCHANT-EQ1\n')
        resp = self.api.post('/api/django/imports/commit/',
                             {'file': f, 'target': 'equipements'}, format='multipart')
        self.assertEqual(resp.data['created'], 0)


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
