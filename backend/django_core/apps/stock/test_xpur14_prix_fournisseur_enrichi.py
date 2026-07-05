"""XPUR14 — PrixFournisseur enrichi : code article fournisseur, paliers de
quantité, validité, import xlsx.

Couvre :
  * le prix effectif retenu suit le bon palier de quantité ;
  * un tarif expiré (date_fin dépassée) n'est plus proposé ;
  * le code article fournisseur s'imprime sur le PDF BCF ;
  * l'export xlsx sort un classeur avec les colonnes attendues ;
  * l'import xlsx de 500 lignes crée + met à jour sans suppression silencieuse
    et remonte un rapport d'erreurs (SKU introuvable, prix invalide).

Run:
    python manage.py test apps.stock.test_xpur14_prix_fournisseur_enrichi -v 2
"""
import datetime
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    Fournisseur, PalierPrixFournisseur, PrixFournisseur, Produit,
    BonCommandeFournisseur,
)
from apps.stock.services import (
    export_prix_fournisseur_xlsx, import_prix_fournisseur_xlsx,
    prix_effectif_fournisseur,
)
from apps.stock.utils.pdf_fournisseur import build_bcf_context

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur14Base(TestCase):
    def setUp(self):
        self.company = _company('xpur14-co')
        self.user = _user(
            self.company, 'xpur14-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Tarif')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X14', sku='OND-XPUR14',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))


class TestPrixEffectifPaliers(Xpur14Base):
    def setUp(self):
        super().setUp()
        self.pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'),
            ref_produit_fournisseur='FRN-REF-42')
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=self.pf, qte_min=10, prix=Decimal('900'))
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=self.pf, qte_min=50, prix=Decimal('800'))

    def test_quantite_sous_le_premier_palier_prend_le_prix_de_base(self):
        prix = prix_effectif_fournisseur(
            self.produit, self.fournisseur, quantite=5)
        self.assertEqual(prix, Decimal('1000'))

    def test_quantite_dans_le_palier_intermediaire(self):
        prix = prix_effectif_fournisseur(
            self.produit, self.fournisseur, quantite=20)
        self.assertEqual(prix, Decimal('900'))

    def test_quantite_dans_le_plus_haut_palier(self):
        prix = prix_effectif_fournisseur(
            self.produit, self.fournisseur, quantite=100)
        self.assertEqual(prix, Decimal('800'))

    def test_sans_palier_prend_le_prix_de_base(self):
        autre_produit = Produit.objects.create(
            company=self.company, nom='Panneau X14', sku='PAN-XPUR14',
            prix_vente=Decimal('900'), prix_achat=Decimal('500'))
        PrixFournisseur.objects.create(
            company=self.company, produit=autre_produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('500'))
        prix = prix_effectif_fournisseur(
            autre_produit, self.fournisseur, quantite=1000)
        self.assertEqual(prix, Decimal('500'))


class TestValiditeTarif(Xpur14Base):
    def test_tarif_expire_non_propose(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'),
            date_fin=datetime.date(2020, 1, 1))
        prix = prix_effectif_fournisseur(
            self.produit, self.fournisseur,
            a_la_date=datetime.date(2026, 1, 1))
        self.assertIsNone(prix)

    def test_tarif_pas_encore_debute_non_propose(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'),
            date_debut=datetime.date(2030, 1, 1))
        prix = prix_effectif_fournisseur(
            self.produit, self.fournisseur,
            a_la_date=datetime.date(2026, 1, 1))
        self.assertIsNone(prix)

    def test_sans_dates_toujours_en_vigueur(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'))
        prix = prix_effectif_fournisseur(self.produit, self.fournisseur)
        self.assertEqual(prix, Decimal('1000'))


class TestRefProduitFournisseurSurPdf(Xpur14Base):
    def test_ref_fournisseur_dans_le_contexte_pdf(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'),
            ref_produit_fournisseur='FRN-REF-99')
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-PDF14',
            fournisseur=self.fournisseur)
        ligne = bc.lignes.create(
            produit=self.produit, quantite=2,
            prix_achat_unitaire=Decimal('1000'))
        context = build_bcf_context(bc)
        self.assertEqual(
            context['ref_produit_fournisseur'][ligne.id], 'FRN-REF-99')

    def test_sans_ref_colonne_vide_comportement_historique(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-PDF14B',
            fournisseur=self.fournisseur)
        ligne = bc.lignes.create(
            produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1000'))
        context = build_bcf_context(bc)
        self.assertEqual(context['ref_produit_fournisseur'][ligne.id], '')


class TestExportImportXlsx(Xpur14Base):
    def test_export_contient_les_colonnes_attendues(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'),
            ref_produit_fournisseur='FRN-1')
        response = export_prix_fournisseur_xlsx(
            self.company, self.fournisseur)
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])

    def _make_xlsx(self, rows, headers=None):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        headers = headers or [
            'sku', 'produit', 'ref_produit_fournisseur', 'prix_achat',
            'date_debut', 'date_fin', 'paliers (qte_min:prix;...)',
        ]
        ws.append(headers)
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_import_cree_et_met_a_jour(self):
        autre_produit = Produit.objects.create(
            company=self.company, nom='Panneau X14b', sku='PAN-XPUR14B',
            prix_vente=Decimal('900'), prix_achat=Decimal('500'))
        # Tarif préexistant pour ce produit — sera MIS À JOUR.
        PrixFournisseur.objects.create(
            company=self.company, produit=autre_produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('400'))

        file_bytes = self._make_xlsx([
            ['OND-XPUR14', 'Onduleur X14', 'FRN-NEW', 1100, None, None,
             '10:1000;50:900'],
            ['PAN-XPUR14B', 'Panneau X14b', '', 550, None, None, ''],
        ])
        result = import_prix_fournisseur_xlsx(
            self.company, self.fournisseur, file_bytes)
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['errors'], [])

        pf = PrixFournisseur.objects.get(
            produit=self.produit, fournisseur=self.fournisseur)
        self.assertEqual(pf.prix_achat, Decimal('1100'))
        self.assertEqual(pf.ref_produit_fournisseur, 'FRN-NEW')
        self.assertEqual(pf.paliers.count(), 2)

        autre_pf = PrixFournisseur.objects.get(
            produit=autre_produit, fournisseur=self.fournisseur)
        self.assertEqual(autre_pf.prix_achat, Decimal('550'))

    def test_import_ne_supprime_jamais_silencieusement(self):
        # Un produit absent du fichier garde son tarif existant.
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'))
        file_bytes = self._make_xlsx([])
        import_prix_fournisseur_xlsx(
            self.company, self.fournisseur, file_bytes)
        self.assertTrue(
            PrixFournisseur.objects.filter(
                produit=self.produit, fournisseur=self.fournisseur).exists())

    def test_import_rapporte_les_erreurs_sku_et_prix(self):
        file_bytes = self._make_xlsx([
            ['SKU-INTROUVABLE', 'X', '', 100, None, None, ''],
            ['OND-XPUR14', 'Onduleur X14', '', 'pas-un-nombre', None, None,
             ''],
        ])
        result = import_prix_fournisseur_xlsx(
            self.company, self.fournisseur, file_bytes)
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(len(result['errors']), 2)

    def test_import_500_lignes(self):
        produits = [
            Produit.objects.create(
                company=self.company, nom=f'Produit X14-{i}',
                sku=f'SKU-X14-{i}', prix_vente=Decimal('100'),
                prix_achat=Decimal('50'))
            for i in range(500)
        ]
        rows = [[p.sku, p.nom, '', 100 + i, None, None, '']
                for i, p in enumerate(produits)]
        file_bytes = self._make_xlsx(rows)
        result = import_prix_fournisseur_xlsx(
            self.company, self.fournisseur, file_bytes)
        self.assertEqual(result['created'], 500)
        self.assertEqual(result['errors'], [])


class TestPrixFournisseurEndpoints(Xpur14Base):
    def test_export_endpoint(self):
        resp = self.api.get(
            '/api/django/stock/prix-fournisseurs/export-xlsx/'
            f'?fournisseur={self.fournisseur.id}')
        self.assertEqual(resp.status_code, 200)

    def test_import_endpoint(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(['sku', 'produit', 'ref_produit_fournisseur',
                   'prix_achat', 'date_debut', 'date_fin', 'paliers'])
        ws.append([self.produit.sku, self.produit.nom, '', 1234, None, None,
                   ''])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile(
            'tarif.xlsx', buf.read(),
            content_type=(
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'))
        resp = self.api.post(
            '/api/django/stock/prix-fournisseurs/import-xlsx/',
            {'fournisseur': self.fournisseur.id, 'file': upload},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
