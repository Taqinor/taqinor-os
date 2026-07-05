"""XPUR26 — Réception e-facture fournisseur (préparation mandat DGI 2026,
entrant).

Couvre :
  * un fichier UBL 2.1 d'exemple crée un brouillon FactureFournisseur correct
    (fournisseur matché par ICE, lignes, TVA, montants) ;
  * le numéro de clearance DGI se stocke et pilote statut_conformite_dgi ;
  * un fichier illisible / sans fournisseur matchable échoue proprement, sans
    créer de facture (dégradation propre) ;
  * tout est INERTE (400, no-op) tant que
    `AchatsParametres.einvoicing_entrant_actif` reste OFF (défaut) — aucune
    régression pour les sociétés qui n'ont pas activé le flag ;
  * l'endpoint `depuis-ubl` crée le brouillon une fois le flag activé.

Run:
    python manage.py test apps.stock.test_xpur26_einvoicing_entrant -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, FactureFournisseur, Fournisseur,
)
from apps.stock.services import (
    creer_facture_fournisseur_depuis_ubl, parse_ubl_invoice,
)

User = get_user_model()

_UBL_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>INV-UBL-042</cbc:ID>
  <cbc:UUID>DGI-CLR-0099</cbc:UUID>
  <cbc:IssueDate>2026-06-15</cbc:IssueDate>
  <cbc:DueDate>2026-07-15</cbc:DueDate>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>Solar Import SARL</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>001234567000089</cbc:CompanyID>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:TaxTotal><cbc:TaxAmount>2000</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount>10000</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount>12000</cbc:TaxInclusiveAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>2</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount>10000</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Name>Onduleur triphasé 10kW</cbc:Name>
      <cac:ClassifiedTaxCategory><cbc:Percent>20</cbc:Percent>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price><cbc:PriceAmount>5000</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>
"""

_UBL_NO_CLEARANCE = _UBL_SAMPLE.replace(
    '<cbc:UUID>DGI-CLR-0099</cbc:UUID>', '')

_UBL_UNKNOWN_SUPPLIER = _UBL_SAMPLE.replace(
    'Solar Import SARL', 'Inconnu Corp').replace(
    '001234567000089', '999999999000000')


def _ubl_file(content=_UBL_SAMPLE, name='facture.xml'):
    return SimpleUploadedFile(
        name, content.encode('utf-8'), content_type='application/xml')


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


class Xpur26Base(TestCase):
    def setUp(self):
        self.company = _company('xpur26-co')
        self.user = _user(
            self.company, 'xpur26-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Solar Import SARL',
            ice='001234567000089')


class TestParseUblInvoice(TestCase):
    def test_parse_champs_et_lignes(self):
        fields = parse_ubl_invoice(_UBL_SAMPLE.encode('utf-8'))
        self.assertEqual(fields['numero'], 'INV-UBL-042')
        self.assertEqual(fields['ice_fournisseur'], '001234567000089')
        self.assertEqual(fields['nom_fournisseur'], 'Solar Import SARL')
        self.assertEqual(fields['montant_ht'], Decimal('10000'))
        self.assertEqual(fields['montant_tva'], Decimal('2000'))
        self.assertEqual(fields['montant_ttc'], Decimal('12000'))
        self.assertEqual(fields['numero_clearance_dgi'], 'DGI-CLR-0099')
        self.assertEqual(len(fields['lignes']), 1)
        ligne = fields['lignes'][0]
        self.assertEqual(ligne['designation'], 'Onduleur triphasé 10kW')
        self.assertEqual(ligne['quantite'], Decimal('2'))
        self.assertEqual(ligne['prix_unitaire_ht'], Decimal('5000'))
        self.assertEqual(ligne['taux_tva'], Decimal('20'))

    def test_xml_illisible_leve_valueerror(self):
        with self.assertRaises(ValueError):
            parse_ubl_invoice(b'<not-valid-xml')

    def test_sans_id_leve_valueerror(self):
        bad = _UBL_SAMPLE.replace('<cbc:ID>INV-UBL-042</cbc:ID>', '')
        with self.assertRaises(ValueError):
            parse_ubl_invoice(bad.encode('utf-8'))


class TestCreerFactureDepuisUbl(Xpur26Base):
    def test_cree_brouillon_correct_avec_clearance(self):
        facture = creer_facture_fournisseur_depuis_ubl(
            company=self.company, user=self.user,
            xml_bytes=_UBL_SAMPLE.encode('utf-8'))
        self.assertEqual(facture.fournisseur_id, self.fournisseur.id)
        self.assertEqual(facture.montant_ht, Decimal('10000'))
        self.assertEqual(facture.montant_tva, Decimal('2000'))
        self.assertEqual(facture.montant_ttc, Decimal('12000'))
        self.assertEqual(facture.ref_fournisseur, 'INV-UBL-042')
        self.assertEqual(facture.numero_clearance_dgi, 'DGI-CLR-0099')
        self.assertEqual(
            facture.statut_conformite_dgi,
            FactureFournisseur.StatutConformiteDgi.CLEARED)
        self.assertEqual(facture.lignes.count(), 1)
        ligne = facture.lignes.first()
        self.assertEqual(ligne.designation, 'Onduleur triphasé 10kW')
        self.assertEqual(ligne.quantite, Decimal('2'))
        self.assertEqual(ligne.prix_unitaire_ht, Decimal('5000'))
        self.assertEqual(ligne.taux_tva, Decimal('20'))
        self.assertIn('UBL', facture.note)

    def test_sans_numero_clearance_statut_non_cleared(self):
        facture = creer_facture_fournisseur_depuis_ubl(
            company=self.company, user=self.user,
            xml_bytes=_UBL_NO_CLEARANCE.encode('utf-8'))
        self.assertIsNone(facture.numero_clearance_dgi)
        self.assertEqual(
            facture.statut_conformite_dgi,
            FactureFournisseur.StatutConformiteDgi.NON_CLEARED)

    def test_facture_manuelle_reste_non_applicable(self):
        # Comportement historique inchangé : une facture créée hors import
        # UBL garde le statut de conformité par défaut.
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-MANUEL',
            fournisseur=self.fournisseur, montant_ttc=Decimal('100'))
        self.assertEqual(
            facture.statut_conformite_dgi,
            FactureFournisseur.StatutConformiteDgi.NON_APPLICABLE)
        self.assertIsNone(facture.numero_clearance_dgi)

    def test_sans_fournisseur_matche_leve_valueerror(self):
        with self.assertRaises(ValueError):
            creer_facture_fournisseur_depuis_ubl(
                company=self.company, user=self.user,
                xml_bytes=_UBL_UNKNOWN_SUPPLIER.encode('utf-8'))
        self.assertEqual(FactureFournisseur.objects.count(), 0)


class TestDepuisUblEndpoint(Xpur26Base):
    def test_endpoint_400_quand_flag_off(self):
        # Défaut = OFF : total no-op, aucune facture créée.
        resp = self.api.post(
            '/api/django/stock/factures-fournisseur/depuis-ubl/',
            {'file': _ubl_file()}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(FactureFournisseur.objects.count(), 0)

    def test_endpoint_cree_brouillon_quand_flag_actif(self):
        parametres = AchatsParametres.for_company(self.company)
        parametres.einvoicing_entrant_actif = True
        parametres.save()

        resp = self.api.post(
            '/api/django/stock/factures-fournisseur/depuis-ubl/',
            {'file': _ubl_file()}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant_ttc']), Decimal('12000'))
        self.assertEqual(resp.data['numero_clearance_dgi'], 'DGI-CLR-0099')
        self.assertEqual(resp.data['statut_conformite_dgi'], 'cleared')

    def test_endpoint_sans_fichier_400(self):
        parametres = AchatsParametres.for_company(self.company)
        parametres.einvoicing_entrant_actif = True
        parametres.save()

        resp = self.api.post(
            '/api/django/stock/factures-fournisseur/depuis-ubl/', {},
            format='multipart')
        self.assertEqual(resp.status_code, 400)
