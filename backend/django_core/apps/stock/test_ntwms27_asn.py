"""NTWMS27 — bordereau EDI ASN (avis d'expédition anticipé).

Critère d'acceptation testé : l'export ASN d'une palette scellée produit un
fichier structuré incluant le SSCC ET toutes les lignes, validable par un
import miroir.

Aucune connexion EDI réelle n'existe (fonction « prête pour EDI ») : aucun
appel réseau, aucune dépendance ajoutée.

Run :
    python manage.py test apps.stock.test_ntwms27_asn -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, LotEntrepot, Produit
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_unite_logistique, exporter_asn,
    importer_asn, sceller_unite_logistique,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms27Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms27-co', 'NTWMS27 Co')
        self.autre = make_company('ntwms27-autre', 'NTWMS27 Autre')
        self.admin = User.objects.create_user(
            username='ntwms27_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS27', is_principal=True)
        self.produit_a = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-NTWMS27',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=60)
        self.produit_b = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', sku='BAT-NTWMS27',
            prix_achat=Decimal('4000'), prix_vente=Decimal('5200'),
            quantite_stock=10)
        self.lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit_b,
            numero_lot='LOT-ASN-1', emplacement=self.emplacement,
            quantite_recue=10, quantite_restante=10)
        self.api = auth(self.admin)

    def _palette_scellee(self):
        unite = creer_unite_logistique(
            company=self.company, type_unite='palette',
            poids_kg=Decimal('420.5'), dimensions='120 × 80 × 145')
        ajouter_ligne_unite_logistique(
            company=self.company, unite=unite, produit=self.produit_a,
            quantite=12)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=unite, produit=self.produit_b,
            quantite=4, lot=self.lot)
        sceller_unite_logistique(unite=unite, user=self.admin)
        unite.refresh_from_db()
        return unite


class TestExportAsn(Ntwms27Base):
    def test_export_contient_le_sscc_et_toutes_les_lignes(self):
        unite = self._palette_scellee()

        bordereau = exporter_asn(unite)

        self.assertEqual(bordereau['unite']['sscc'], unite.sscc)
        self.assertEqual(len(bordereau['unite']['sscc']), 18)
        self.assertEqual(len(bordereau['lignes']), 2)
        self.assertEqual(bordereau['totaux']['quantite_totale'], 16)
        lot_ligne = next(ligne for ligne in bordereau['lignes']
                         if ligne['sku'] == 'BAT-NTWMS27')
        self.assertEqual(lot_ligne['numero_lot'], 'LOT-ASN-1')
        self.assertEqual(lot_ligne['quantite'], 4)

    def test_unite_non_scellee_refusee(self):
        unite = creer_unite_logistique(
            company=self.company, type_unite='colis')
        ajouter_ligne_unite_logistique(
            company=self.company, unite=unite, produit=self.produit_a,
            quantite=1)
        with self.assertRaises(ValueError):
            exporter_asn(unite)


class TestImportMiroirAsn(Ntwms27Base):
    def test_import_miroir_valide_l_export(self):
        unite = self._palette_scellee()
        rapport = importer_asn(self.company, exporter_asn(unite))

        self.assertTrue(rapport['valide'])
        self.assertEqual(rapport['erreurs'], [])
        self.assertTrue(rapport['unite_connue'])
        self.assertEqual(len(rapport['lignes']), 2)
        self.assertTrue(all(ligne['produit_id']
                            for ligne in rapport['lignes']))

    def test_sscc_falsifie_refuse(self):
        unite = self._palette_scellee()
        bordereau = exporter_asn(unite)
        bordereau['unite']['sscc'] = '1' * 18  # clé de contrôle fausse
        rapport = importer_asn(self.company, bordereau)
        self.assertFalse(rapport['valide'])
        self.assertTrue(any('SSCC' in e for e in rapport['erreurs']))

    def test_sku_inconnu_signale(self):
        unite = self._palette_scellee()
        bordereau = exporter_asn(unite)
        bordereau['lignes'][0]['sku'] = 'SKU-FANTOME'
        rapport = importer_asn(self.company, bordereau)
        self.assertFalse(rapport['valide'])
        self.assertIsNone(rapport['lignes'][0]['produit_id'])

    def test_version_inattendue_signalee(self):
        unite = self._palette_scellee()
        bordereau = exporter_asn(unite)
        bordereau['version'] = 'EDIFACT-D96A'
        self.assertFalse(importer_asn(self.company, bordereau)['valide'])

    def test_bordereau_vide_refuse(self):
        rapport = importer_asn(self.company, {'version': 'TAQINOR-ASN-1'})
        self.assertFalse(rapport['valide'])

    def test_bordereau_illisible_ne_casse_pas(self):
        rapport = importer_asn(self.company, 'pas un objet')
        self.assertFalse(rapport['valide'])

    def test_unite_d_une_autre_societe_est_inconnue(self):
        unite = self._palette_scellee()
        rapport = importer_asn(self.autre, exporter_asn(unite))
        self.assertFalse(rapport['unite_connue'])


class TestEndpointsAsn(Ntwms27Base):
    def test_export_via_api(self):
        unite = self._palette_scellee()
        reponse = self.api.get(
            f'/api/django/stock/unites-logistiques/{unite.id}/export-asn/')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['unite']['sscc'], unite.sscc)
        self.assertEqual(len(reponse.data['lignes']), 2)

    def test_export_telechargeable(self):
        unite = self._palette_scellee()
        reponse = self.api.get(
            f'/api/django/stock/unites-logistiques/{unite.id}/export-asn/',
            {'telecharger': '1'})
        self.assertIn('attachment', reponse['Content-Disposition'])

    def test_export_unite_non_scellee_400(self):
        unite = creer_unite_logistique(
            company=self.company, type_unite='colis')
        reponse = self.api.get(
            f'/api/django/stock/unites-logistiques/{unite.id}/export-asn/')
        self.assertEqual(reponse.status_code, 400)

    def test_import_via_api(self):
        unite = self._palette_scellee()
        bordereau = exporter_asn(unite)
        reponse = self.api.post(
            '/api/django/stock/unites-logistiques/import-asn/',
            bordereau, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['valide'])
