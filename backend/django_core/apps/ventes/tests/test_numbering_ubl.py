"""Tests N31 (audit numérotation) + N38 (export UBL 2.1 aperçu brouillon)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneFacture
from apps.ventes.utils.numbering_audit import find_gaps_and_dupes, audit_company
from apps.ventes.utils.ubl import build_ubl_xml

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='num-co', nom='Num Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, **extra):
    return Client.objects.create(
        company=company, nom='Doe', prenom='Jane',
        email=extra.pop('email', 'jane@example.com'),
        telephone='+212600000099', adresse='Rabat', **extra)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestFindGapsAndDupes(TestCase):
    """Le cœur pur de l'audit (sans Django/DB)."""

    def test_no_gap(self):
        refs = ['DEV-202606-0001', 'DEV-202606-0002', 'DEV-202606-0003']
        self.assertEqual(find_gaps_and_dupes(refs), [])

    def test_detects_missing_number(self):
        refs = ['DEV-202606-0001', 'DEV-202606-0003']
        out = find_gaps_and_dupes(refs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['radical'], 'DEV-202606')
        self.assertEqual(out[0]['manquants'], [2])
        self.assertEqual(out[0]['doublons'], [])

    def test_detects_duplicate(self):
        refs = ['FAC-202606-0001', 'FAC-202606-0001', 'FAC-202606-0002']
        out = find_gaps_and_dupes(refs)
        self.assertEqual(out[0]['doublons'], [1])

    def test_groups_by_month(self):
        refs = ['DEV-202605-0001', 'DEV-202606-0002']
        out = find_gaps_and_dupes(refs)
        # Le mois 202606 commence à 2 → trou [1] ; le mois 202605 est complet.
        radicaux = {g['radical']: g['manquants'] for g in out}
        self.assertEqual(radicaux.get('DEV-202606'), [1])
        self.assertNotIn('DEV-202605', radicaux)

    def test_ignores_unparseable(self):
        self.assertEqual(find_gaps_and_dupes(['', None, 'NOSUFFIX']), [])


class TestNumerotationAuditEndpoint(TestCase):
    def setUp(self):
        self.company = make_company(slug='audit-co', nom='Audit Co')
        self.admin = User.objects.create_user(
            username='audit_admin', password='x', role_legacy='admin',
            company=self.company)
        self.resp = User.objects.create_user(
            username='audit_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, num):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj)

    def test_reports_gap_after_deletion(self):
        self._devis(1)
        d2 = self._devis(2)
        self._devis(3)
        d2.delete()  # laisse un trou au numéro 2
        rapport = audit_company(self.company)
        self.assertFalse(rapport['conforme'])
        self.assertEqual(rapport['devis'][0]['manquants'], [2])
        self.assertEqual(rapport['total_manquants'], 1)

    def test_endpoint_admin_only(self):
        # responsable (non admin) refusé
        r = auth(self.resp).get('/api/django/ventes/numerotation-audit/')
        self.assertEqual(r.status_code, 403)
        # admin autorisé
        r = auth(self.admin).get('/api/django/ventes/numerotation-audit/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('devis', r.data)


class TestNumerotationPreviewEndpoint(TestCase):
    """L770/L786 — aperçu du prochain numéro RÉEL par type de pièce."""

    def setUp(self):
        self.company = make_company(slug='prev-co', nom='Prev Co')
        self.admin = User.objects.create_user(
            username='prev_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = make_client(self.company)

    def test_preview_reflects_highest_sequence(self):
        # Sans aucune pièce, l'aperçu repart à 1 pour chaque type.
        r = auth(self.admin).get('/api/django/ventes/numerotation-preview/')
        self.assertEqual(r.status_code, 200, r.data)
        for key in ('devis', 'facture', 'avoir', 'bon_commande'):
            self.assertIn(key, r.data)
        self.assertTrue(r.data['devis'].endswith('-0001'))
        # Avec un devis n°7, l'aperçu devient n°8 (plus-haut-utilisé + 1).
        Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0007',
            client=self.client_obj)
        r2 = auth(self.admin).get('/api/django/ventes/numerotation-preview/')
        self.assertEqual(r2.data['devis'], f'DEV-{MONTH}-0008')
        # Le facture/avoir/bon_commande restent au n°1 (séquences distinctes).
        self.assertTrue(r2.data['facture'].endswith('-0001'))
        self.assertTrue(r2.data['avoir'].endswith('-0001'))
        self.assertTrue(r2.data['bon_commande'].endswith('-0001'))


class TestUblExport(TestCase):
    def setUp(self):
        self.company = make_company(slug='ubl-co', nom='UBL Co')
        self.user = User.objects.create_user(
            username='ubl_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=self.company)
        prof.nom = 'UBL Co'
        prof.ice = 'ICE001122334'
        prof.identifiant_fiscal = 'IF777'
        prof.rc = 'RC888'
        prof.save()
        self.client_obj = make_client(
            self.company, email='b2b@example.com',
            type_client='entreprise', ice='ICE999888777')

    def _facture(self):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-5001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            conditions_paiement='Virement à 30 jours')
        prod = Produit.objects.create(
            company=self.company, nom='Panneau', sku='UBL-PV-1',
            prix_vente=Decimal('1000'), quantite_stock=50, tva=Decimal('10.00'))
        LigneFacture.objects.create(
            facture=facture, produit=prod, designation='Panneau PV 550W',
            quantite=Decimal('4'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('10.00'))
        return facture

    def test_build_xml_contains_legal_ids_and_line_vat(self):
        facture = self._facture()
        from apps.parametres.models import CompanyProfile
        xml = build_ubl_xml(facture, CompanyProfile.get(company=self.company))
        self.assertIn('APERCU BROUILLON', xml)
        self.assertIn('ICE001122334', xml)   # ICE vendeur
        self.assertIn('IF777', xml)           # IF vendeur
        self.assertIn('ICE999888777', xml)    # ICE client (B2B)
        self.assertIn('Panneau PV 550W', xml)
        self.assertIn('10.00', xml)           # taux TVA de ligne
        self.assertIn('Invoice', xml)         # racine UBL

    def test_endpoint_returns_xml(self):
        facture = self._facture()
        r = self.api.get(f'/api/django/ventes/factures/{facture.id}/ubl/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/xml')
        body = r.content.decode('utf-8')
        self.assertIn('ICE001122334', body)
        self.assertIn('TaxInclusiveAmount', body)
        # La clé MinIO est mémorisée sur la facture (stockage best-effort).
        facture.refresh_from_db()
        # fichier_ubl peut être None si MinIO indisponible, sinon une clé .xml.
        if facture.fichier_ubl:
            self.assertTrue(facture.fichier_ubl.endswith('.xml'))
