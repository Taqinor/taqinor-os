"""PUB96/PUB98 — Tests du pont comptable (adsengine → compta).

Prouve : la dépense publicitaire du mois entre en compta comme écriture
BROUILLON équilibrée (débit 6144 / crédit 4486), JAMAIS validée, JAMAIS de double
écriture (idempotence par période), NO-OP à dépense nulle, scoping société ; et
l'ingestion d'une facture Meta pose une facture fournisseur BROUILLON avec TVA
auto-liquidée compensée + signale l'écart vs spend synchronisé.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import compta_bridge
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot
from apps.compta.models import EcritureComptable, LigneEcriture


class ComptaBridgeSpendTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Pub Co', slug='pub-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Solaire', status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _snap(self, day, spend, camp=None):
        camp = camp or self.camp
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=camp.pk,
            date=day, spend=Decimal(spend))

    def test_monthly_spend_sums_campaign_snapshots(self):
        self._snap(datetime.date(2026, 7, 3), '120.50')
        self._snap(datetime.date(2026, 7, 20), '80.00')
        self._snap(datetime.date(2026, 6, 30), '999.00')  # autre mois : exclu
        total = compta_bridge.monthly_ad_spend(self.company, 2026, 7)
        self.assertEqual(total, Decimal('200.50'))

    def test_book_creates_balanced_draft_entry(self):
        self._snap(datetime.date(2026, 7, 3), '120.50')
        self._snap(datetime.date(2026, 7, 20), '80.00')
        ecriture = compta_bridge.book_monthly_ad_spend(
            self.company, year=2026, month=7)
        self.assertIsNotNone(ecriture)
        # Jamais validée automatiquement.
        self.assertEqual(ecriture.statut, EcritureComptable.Statut.BROUILLON)
        # Équilibrée : débit 6144 = crédit 4486 = 200.50.
        lignes = list(LigneEcriture.objects.filter(ecriture=ecriture))
        self.assertEqual(len(lignes), 2)
        debit = next(li for li in lignes if li.compte.numero == '6144')
        credit = next(li for li in lignes if li.compte.numero == '4486')
        self.assertEqual(debit.debit, Decimal('200.50'))
        self.assertEqual(credit.credit, Decimal('200.50'))
        self.assertEqual(ecriture.source_type, compta_bridge.SOURCE_DEPENSE)
        self.assertEqual(ecriture.source_id, 202607)

    def test_idempotent_no_double_entry(self):
        self._snap(datetime.date(2026, 7, 3), '200.00')
        first = compta_bridge.book_monthly_ad_spend(
            self.company, year=2026, month=7)
        second = compta_bridge.book_monthly_ad_spend(
            self.company, year=2026, month=7)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.company,
                source_type=compta_bridge.SOURCE_DEPENSE).count(),
            1)

    def test_noop_on_zero_spend(self):
        ecriture = compta_bridge.book_monthly_ad_spend(
            self.company, year=2026, month=7)
        self.assertIsNone(ecriture)
        self.assertEqual(EcritureComptable.objects.count(), 0)

    def test_company_scoped(self):
        other = Company.objects.create(nom='Autre', slug='autre-co')
        self._snap(datetime.date(2026, 7, 3), '200.00')
        compta_bridge.book_monthly_ad_spend(self.company, year=2026, month=7)
        # Aucune écriture pour l'autre société (dépense d'une seule).
        self.assertEqual(
            EcritureComptable.objects.filter(company=other).count(), 0)
        self.assertEqual(
            compta_bridge.monthly_ad_spend(other, 2026, 7), Decimal('0'))


class ComptaBridgeInvoiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fac Co', slug='fac-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Solaire', status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=datetime.date(2026, 7, 10), spend=Decimal('1000.00'))

    def test_invoice_draft_with_reverse_charge_vat(self):
        result = compta_bridge.ingest_meta_invoice(
            self.company, year=2026, month=7, montant_ht='1000.00')
        ecriture = result['ecriture']
        self.assertEqual(ecriture.statut, EcritureComptable.Statut.BROUILLON)
        self.assertEqual(result['montant_tva'], Decimal('200.00'))
        # Écriture équilibrée avec TVA auto-liquidée compensée.
        lignes = {li.compte.numero: li for li in
                  LigneEcriture.objects.filter(ecriture=ecriture)}
        self.assertEqual(lignes['34552'].debit, Decimal('200.00'))
        self.assertEqual(lignes['44552'].credit, Decimal('200.00'))
        total_debit = sum(li.debit for li in ecriture.lignes.all())
        total_credit = sum(li.credit for li in ecriture.lignes.all())
        self.assertEqual(total_debit, total_credit)

    def test_ecart_vs_spend_signaled(self):
        result = compta_bridge.ingest_meta_invoice(
            self.company, year=2026, month=7, montant_ht='1050.00')
        self.assertEqual(result['spend_synchronise'], Decimal('1000.00'))
        self.assertEqual(result['ecart_vs_spend'], Decimal('50.00'))

    def test_invoice_idempotent(self):
        first = compta_bridge.ingest_meta_invoice(
            self.company, year=2026, month=7, montant_ht='1000.00')
        second = compta_bridge.ingest_meta_invoice(
            self.company, year=2026, month=7, montant_ht='1000.00')
        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(first['ecriture'].pk, second['ecriture'].pk)

    def test_parse_csv_amount(self):
        csv_content = 'date,amount\n2026-07-01,600.00\n2026-07-15,400.00\n'
        self.assertEqual(
            compta_bridge.parse_meta_invoice_csv(csv_content),
            Decimal('1000.00'))

    def test_parse_csv_graceful_on_garbage(self):
        self.assertEqual(
            compta_bridge.parse_meta_invoice_csv('not,a,valid\ninvoice,x,y'),
            Decimal('0'))
