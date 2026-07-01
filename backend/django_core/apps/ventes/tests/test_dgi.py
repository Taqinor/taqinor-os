"""N105 — Capacité DGI LOCALE : export UBL 2.1 + validateur, gardés par
l'interrupteur maître ``CompanyProfile.dgi_export_actif`` (défaut OFF).

Couvre :
  * OFF par défaut : sortie du sérialiseur facture inchangée (aucun champ DGI
    visible), endpoints DGI injoignables (404), comportement byte-identique.
  * ``build_ubl_xml`` : XML bien formé portant ICE client + TVA par ligne +
    totaux, sans aucun prix d'achat / marge.
  * ``validate_dgi_conformity`` : signale l'ICE client manquant (B2B), passe
    sur une facture complète.
  * Portée société respectée (export hors société interdit / 404).
"""
from decimal import Decimal
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.dgi import (
    build_ubl_xml, validate_dgi_conformity, is_dgi_enabled)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def seller_profile(company, **extra):
    prof = CompanyProfile.get(company=company)
    prof.nom = extra.get('nom', 'Vendeur SARL')
    prof.ice = extra.get('ice', 'ICE-SELLER-001')
    prof.identifiant_fiscal = extra.get('identifiant_fiscal', 'IF-12345')
    prof.rc = extra.get('rc', 'RC-67890')
    if 'dgi_export_actif' in extra:
        prof.dgi_export_actif = extra['dgi_export_actif']
    prof.save()
    return prof


class DgiTestBase(TestCase):
    def setUp(self):
        self.company = make_company('dgi-co', 'DGI Co')
        self.user = User.objects.create_user(
            username='dgi_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.profile = seller_profile(self.company)
        self.client_b2b = Client.objects.create(
            company=self.company, nom='Acme', prenom='Pro',
            email='pro@acme.ma', telephone='+212600000001', adresse='Casa',
            type_client='entreprise', ice='ICE-CLIENT-999')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='DGI-PV-1',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=50, tva=Decimal('10.00'))

    def _facture(self, client=None):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-9001',
            client=client or self.client_b2b, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            conditions_paiement='Virement à 30 jours')
        LigneFacture.objects.create(
            facture=facture, produit=self.produit,
            designation='Panneau PV 550W', quantite=Decimal('4'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('10.00'))
        return facture


class TestToggleOffInvisible(DgiTestBase):
    """OFF par défaut : capacité totalement invisible, rien ne change."""

    def test_toggle_defaults_off(self):
        # Profil neuf = interrupteur OFF.
        fresh = make_company('dgi-fresh', 'Fresh Co')
        prof = CompanyProfile.get(company=fresh)
        self.assertFalse(prof.dgi_export_actif)
        self.assertFalse(is_dgi_enabled(fresh))

    def test_facture_serializer_has_no_dgi_field(self):
        facture = self._facture()
        r = self.api.get(f'/api/django/ventes/factures/{facture.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        # Aucun champ DGI ne fuit dans la facture (le toggle vit sur le profil).
        keys = set(r.data.keys())
        self.assertNotIn('dgi_export_actif', keys)
        self.assertFalse([k for k in keys if 'dgi' in k.lower()])

    def test_endpoints_404_when_off(self):
        facture = self._facture()
        r1 = self.api.get(
            f'/api/django/ventes/factures/{facture.id}/dgi-export/')
        r2 = self.api.get(
            f'/api/django/ventes/factures/{facture.id}/dgi-conformite/')
        self.assertEqual(r1.status_code, 404)
        self.assertEqual(r2.status_code, 404)

    def test_endpoints_work_when_on(self):
        seller_profile(self.company, dgi_export_actif=True)
        facture = self._facture()
        r1 = self.api.get(
            f'/api/django/ventes/factures/{facture.id}/dgi-export/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1['Content-Type'], 'application/xml')
        self.assertIn('ICE-CLIENT-999', r1.content.decode('utf-8'))
        r2 = self.api.get(
            f'/api/django/ventes/factures/{facture.id}/dgi-conformite/')
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.data['conforme'])
        self.assertEqual(r2.data['problemes'], [])


class TestBuildUblXml(DgiTestBase):
    def test_xml_well_formed_with_ice_and_line_vat(self):
        facture = self._facture()
        xml = build_ubl_xml(facture, self.profile)
        # Bien formé.
        root = ET.fromstring(
            xml.split('?>', 1)[1].split('-->', 1)[1])
        self.assertTrue(root.tag.endswith('Invoice'))
        # ICE émetteur + client présents.
        self.assertIn('ICE-SELLER-001', xml)
        self.assertIn('ICE-CLIENT-999', xml)
        # TVA par ligne (10 %) + totaux.
        self.assertIn('10.00', xml)
        self.assertIn('TaxInclusiveAmount', xml)
        self.assertIn('Panneau PV 550W', xml)

    def test_no_buy_price_or_margin_in_xml(self):
        facture = self._facture()
        xml = build_ubl_xml(facture, self.profile)
        # Le prix d'achat (700) et toute mention de marge ne doivent jamais
        # apparaître. Seuls prix de vente (1000) et total HT figurent.
        self.assertNotIn('700', xml)
        self.assertNotIn('prix_achat', xml)
        self.assertNotIn('marge', xml.lower())
        self.assertIn('1000', xml)

    def test_xml_resolves_profile_when_omitted(self):
        facture = self._facture()
        # profile None → résolu depuis la société : même ICE émetteur.
        xml = build_ubl_xml(facture)
        self.assertIn('ICE-SELLER-001', xml)

    def test_dc25_currency_from_facture_devise(self):
        # La devise du document prime : facture en EUR → UBL en EUR.
        facture = self._facture()
        facture.devise = 'EUR'
        facture.save(update_fields=['devise'])
        xml = build_ubl_xml(facture, self.profile)
        self.assertIn('>EUR<', xml)          # DocumentCurrencyCode
        self.assertIn('currencyID="EUR"', xml)
        self.assertNotIn('>MAD<', xml)

    def test_dc25_currency_falls_back_to_company_profile(self):
        # Facture SANS devise (chaîne vide) → repli sur la devise par défaut de
        # la société (CompanyProfile.devise_defaut), plus jamais « MAD » en dur.
        self.profile.devise_defaut = 'USD'
        self.profile.save(update_fields=['devise_defaut'])
        facture = self._facture()
        facture.devise = ''
        facture.save(update_fields=['devise'])
        xml = build_ubl_xml(facture, self.profile)
        self.assertIn('>USD<', xml)
        self.assertIn('currencyID="USD"', xml)

    def test_dc25_ultimate_fallback_is_mad(self):
        # Ni devise document ni devise société → repli ultime « MAD ».
        self.profile.devise_defaut = ''
        self.profile.save(update_fields=['devise_defaut'])
        facture = self._facture()
        facture.devise = ''
        facture.save(update_fields=['devise'])
        xml = build_ubl_xml(facture, self.profile)
        self.assertIn('>MAD<', xml)


class TestValidateConformity(DgiTestBase):
    def test_complete_b2b_facture_is_conform(self):
        facture = self._facture()
        problemes = validate_dgi_conformity(facture, self.profile)
        self.assertEqual(problemes, [])

    def test_flags_missing_client_ice_b2b(self):
        client_sans_ice = Client.objects.create(
            company=self.company, nom='Pro2', prenom='Sans',
            email='sansice@acme.ma', telephone='+212600000002',
            adresse='Rabat', type_client='entreprise')
        facture = self._facture(client=client_sans_ice)
        problemes = validate_dgi_conformity(facture, self.profile)
        self.assertTrue(any('ICE du client' in p for p in problemes), problemes)

    def test_flags_missing_seller_ids(self):
        bare = make_company('dgi-bare', 'Bare Co')
        prof = CompanyProfile.get(company=bare)
        prof.nom = ''
        prof.ice = ''
        prof.identifiant_fiscal = ''
        prof.rc = ''
        prof.save()
        client = Client.objects.create(
            company=bare, nom='X', prenom='Y', email='x@y.ma',
            telephone='+212600000003', adresse='Fes')
        produit = Produit.objects.create(
            company=bare, nom='P', sku='BARE-1', prix_vente=Decimal('10'),
            quantite_stock=5, tva=Decimal('20'))
        facture = Facture.objects.create(
            company=bare, reference=f'FAC-{MONTH}-9050', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Service',
            quantite=Decimal('1'), prix_unitaire=Decimal('10'),
            taux_tva=Decimal('20'))
        problemes = validate_dgi_conformity(facture, prof)
        self.assertTrue(any('ICE du vendeur' in p for p in problemes))
        self.assertTrue(any('IF' in p for p in problemes))
        self.assertTrue(any('RC' in p for p in problemes))


class TestCompanyScoping(DgiTestBase):
    def test_export_endpoint_scoped_to_own_company(self):
        # Société armée, mais l'utilisateur appartient à une AUTRE société :
        # la facture n'est pas dans son périmètre → 404 (jamais d'export
        # transversal).
        other = make_company('dgi-other', 'Other Co')
        seller_profile(other, dgi_export_actif=True)
        other_user = User.objects.create_user(
            username='dgi_other', password='x', role_legacy='responsable',
            company=other)
        seller_profile(self.company, dgi_export_actif=True)
        facture = self._facture()  # appartient à self.company
        r = auth(other_user).get(
            f'/api/django/ventes/factures/{facture.id}/dgi-export/')
        self.assertEqual(r.status_code, 404)
