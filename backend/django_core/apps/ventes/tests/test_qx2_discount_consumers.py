"""QX2 — la remise globale atteint les AUTRES consommateurs du montant.

Trois consommateurs ignoraient auparavant ``remise_globale`` (KPI fondateur,
valeur Meta CAPI, export UBL/DGI) :

  * l'export UBL ``LegalMonetaryTotal.PayableAmount`` == TTC remisé (+ un
    AllowanceCharge documentant la remise, cohérence UBL) ;
  * la valeur de conversion CAPI == TTC remisé de l'option acceptée ;
  * (le CA des classements reporting est couvert par les tests reporting ;
    il consomme la même chaîne canonique QX1).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
from apps.ventes.utils.ubl import build_ubl_xml

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _q(x):
    return Decimal(x).quantize(Decimal('0.01'))


class Qx2UblDiscountTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx2-co', defaults={'nom': 'QX2 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX2',
            telephone='+212600000042')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='QX2-PV',
            prix_vente=Decimal('1000'), quantite_stock=100)

    def _profile(self):
        from apps.parametres.models import CompanyProfile
        return CompanyProfile.get(company=self.company)

    def test_ubl_payable_amount_is_discounted(self):
        # 10×1000 = 10000 HT ; remise 15 % → 8500 HT ; TVA 1700 ; TTC 10200.
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-QX2001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('15.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        self.assertEqual(_q(facture.total_ht), Decimal('8500.00'))
        self.assertEqual(_q(facture.total_ttc), Decimal('10200.00'))

        xml = build_ubl_xml(facture, self._profile(), currency='MAD')
        # PayableAmount = TTC remisé ; l'AllowanceCharge documente la remise.
        self.assertIn('>10200.00<', xml)
        self.assertIn('AllowanceCharge', xml)
        self.assertIn('Remise globale', xml)
        # LineExtensionAmount (brut) = 10000 ; TaxExclusive (net) = 8500.
        self.assertIn('>10000.00<', xml)
        self.assertIn('>8500.00<', xml)

    def test_ubl_no_remise_has_no_allowance(self):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-QX2002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Panneau',
            quantite=Decimal('5'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        xml = build_ubl_xml(facture, self._profile(), currency='MAD')
        self.assertNotIn('AllowanceCharge', xml)
        self.assertIn('>6000.00<', xml)  # TTC brut = TTC (pas de remise)


class Qx2CapiValueTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx2capi-co', defaults={'nom': 'QX2 CAPI Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Capi',
            telephone='+212600000043')

    def test_capi_value_uses_discounted_ttc(self):
        from unittest import mock
        from django.test import override_settings
        from apps.ventes.services import _fire_capi_signed_quote

        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX2C01',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('10.00'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='QX2C-PV',
            prix_vente=Decimal('1000'), quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        # 10000 HT − 10 % = 9000 HT ; TTC 10800.
        mock_resp = mock.MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.Mock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"events_received": 1}'
        with override_settings(META_CAPI_ACCESS_TOKEN='T',
                               META_CAPI_PIXEL_ID='123'):
            with mock.patch('urllib.request.urlopen',
                            return_value=mock_resp) as m:
                _fire_capi_signed_quote(devis=devis)
                body = m.call_args[0][0].data.decode()
        # La valeur envoyée est le TTC remisé (10800), pas le brut (12000).
        self.assertIn('10800', body)
        self.assertNotIn('12000', body)
