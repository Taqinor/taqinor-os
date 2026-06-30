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
