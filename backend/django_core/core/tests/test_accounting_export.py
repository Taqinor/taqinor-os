"""Tests FG377 — pont comptable Sage/CEGID (export one-way, pur).

Couvre :
  * formatage montant + date FR ;
  * validate_entries détecte champs manquants + déséquilibre ;
  * to_sage_pnm : en-tête tabulé + lignes ;
  * to_cegid_csv : en-tête point-virgule + lignes ;
  * export_entries dispatch + format inconnu → ValueError ;
  * transformation PURE : aucun import d'app domaine, pas de DB.
"""
from django.test import SimpleTestCase

from core import accounting_export as acc


_ENTRIES = [
    {'journal': 'VT', 'date': '2026-06-30', 'compte': '411000',
     'piece': 'F-001', 'libelle': 'Facture F-001', 'debit': 1200.0,
     'credit': 0.0},
    {'journal': 'VT', 'date': '2026-06-30', 'compte': '707000',
     'piece': 'F-001', 'libelle': 'Vente HT', 'debit': 0.0,
     'credit': 1200.0},
]


class HelperTests(SimpleTestCase):
    def test_fmt_amount(self):
        self.assertEqual(acc._fmt_amount(1200), '1200.00')
        self.assertEqual(acc._fmt_amount(None), '0.00')
        self.assertEqual(acc._fmt_amount('bad'), '0.00')

    def test_norm_date(self):
        self.assertEqual(acc._norm_date('2026-06-30'), '30/06/2026')
        self.assertEqual(acc._norm_date(''), '')


class ValidateTests(SimpleTestCase):
    def test_balanced_ok(self):
        self.assertEqual(acc.validate_entries(_ENTRIES), [])

    def test_unbalanced_detected(self):
        bad = [{'journal': 'VT', 'compte': '4', 'debit': 10, 'credit': 0}]
        errs = acc.validate_entries(bad)
        self.assertTrue(any('Déséquilibre' in e for e in errs))

    def test_missing_fields(self):
        errs = acc.validate_entries([{'debit': 0, 'credit': 0}])
        self.assertTrue(any('journal' in e for e in errs))
        self.assertTrue(any('compte' in e for e in errs))


class FormatTests(SimpleTestCase):
    def test_sage_pnm(self):
        out = acc.to_sage_pnm(_ENTRIES)
        lines = out.strip().split('\n')
        self.assertEqual(lines[0].split('\t')[0], 'journal')
        self.assertIn('411000', out)
        self.assertIn('30/06/2026', out)
        self.assertEqual(len(lines), 3)  # en-tête + 2

    def test_cegid_csv(self):
        out = acc.to_cegid_csv(_ENTRIES)
        self.assertTrue(out.startswith('Journal;Date;Compte'))
        self.assertIn('707000', out)

    def test_export_dispatch_and_unknown(self):
        self.assertIn('411000', acc.export_entries(_ENTRIES, 'sage'))
        self.assertIn('411000', acc.export_entries(_ENTRIES, 'cegid'))
        with self.assertRaises(ValueError):
            acc.export_entries(_ENTRIES, 'xxx')


class QuickBooksIifTests(SimpleTestCase):
    """NTAPI37 — pont comptable QuickBooks (IIF General Journal)."""

    def test_norm_date_us(self):
        self.assertEqual(acc._norm_date_us('2026-06-30'), '06/30/2026')
        self.assertEqual(acc._norm_date_us(''), '')

    def test_signed_amount_debit_positive_credit_negative(self):
        self.assertEqual(
            acc._signed_amount({'debit': 1200, 'credit': 0}), '1200.00')
        self.assertEqual(
            acc._signed_amount({'debit': 0, 'credit': 1200}), '-1200.00')
        self.assertEqual(acc._signed_amount({}), '0.00')

    def test_header_and_footer_markers(self):
        out = acc.to_quickbooks_iif(_ENTRIES)
        lines = out.strip('\n').split('\n')
        self.assertEqual(lines[0].split('\t')[0], '!TRNS')
        self.assertEqual(lines[1].split('\t')[0], '!SPL')
        self.assertEqual(lines[2], '!ENDTRNS')
        self.assertTrue(out.strip().endswith('ENDTRNS'))

    def test_single_transaction_trns_then_spl(self):
        # _ENTRIES = 2 lignes de la MÊME pièce F-001 -> 1 transaction.
        out = acc.to_quickbooks_iif(_ENTRIES)
        data_lines = [ln for ln in out.strip('\n').split('\n')[3:] if ln]
        self.assertEqual(data_lines[0].split('\t')[0], 'TRNS')
        self.assertEqual(data_lines[1].split('\t')[0], 'SPL')
        self.assertEqual(data_lines[2], 'ENDTRNS')
        self.assertEqual(len(data_lines), 3)

    def test_amounts_net_to_zero_per_transaction(self):
        out = acc.to_quickbooks_iif(_ENTRIES)
        rows = [ln.split('\t') for ln in out.strip('\n').split('\n')[3:]
                if ln and ln != 'ENDTRNS']
        total = sum(float(r[6]) for r in rows)  # colonne AMOUNT
        self.assertEqual(round(total, 2), 0.0)

    def test_multiple_pieces_become_multiple_transactions(self):
        entries = _ENTRIES + [
            {'journal': 'VT', 'date': '2026-06-30', 'compte': '411000',
             'piece': 'F-002', 'libelle': 'Facture F-002', 'debit': 500.0,
             'credit': 0.0},
            {'journal': 'VT', 'date': '2026-06-30', 'compte': '707000',
             'piece': 'F-002', 'libelle': 'Vente HT', 'debit': 0.0,
             'credit': 500.0},
        ]
        out = acc.to_quickbooks_iif(entries)
        self.assertEqual(out.count('TRNS\t1\t'), 1)
        self.assertEqual(out.count('TRNS\t2\t'), 1)
        self.assertEqual(out.count('ENDTRNS'), 3)  # 1 en-tête + 2 clôtures

    def test_quickbooks_iif_dispatch_via_export_entries(self):
        out = acc.export_entries(_ENTRIES, 'quickbooks_iif')
        self.assertIn('!TRNS', out)
        self.assertIn('411000', out)
