"""QJR618 — le PDF premium résidentiel (format par défaut) imprime les
intertitres de section, les lignes de note et les options proposées.

EN DIRECT (30/09) : le PDF full de DEV-202609-0011 ne contenait ni la section
ni la note tapées ; seul le une-page les lisait. D-QJR5-6 : sections et notes
sont un texte CLIENT, imprimé ; l'add-on optionnel est proposé HORS total avec
le seul ``total_ttc`` du builder (QJR616), au centime (QJR614).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_pdf_residentiel_sections_options"
"""
import re
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, tag

from apps.stock.models import Produit
from apps.ventes.models import LigneDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


def _norm(texte):
    return re.sub(r'\s+', ' ', texte).strip().lower()


@tag('pdf')
class TestPdfResidentielSectionsOptions(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, ref, avec_structure=True):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500', '10'),
            ('Onduleur réseau 5kW', '1', '9000', '20'),
        ], remise_globale='5', reference=ref)
        LigneDevis.objects.filter(devis=devis).update(ordre=1)
        if avec_structure:
            LigneDevis.objects.create(
                devis=devis, produit=None, designation='Section Toiture QJR618',
                quantite=None, prix_unitaire=None, remise=Decimal('0'),
                taux_tva=None, type_ligne='section', ordre=0)
            LigneDevis.objects.create(
                devis=devis, produit=None,
                designation='Note visible pose sous quinze jours',
                quantite=None, prix_unitaire=None, remise=Decimal('0'),
                taux_tva=None, type_ligne='note', ordre=2)
            produit = Produit.objects.create(
                company=self.company, nom='Garantie étendue QJR618',
                sku=f'{ref}-GAR', prix_vente=Decimal('1000'),
                prix_achat=Decimal('7'), quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit,
                designation='Garantie étendue QJR618', quantite=Decimal('1'),
                prix_unitaire=Decimal('1000'), remise=Decimal('0'),
                taux_tva=Decimal('20.00'), optionnelle=True, ordre=3)
        return devis

    def _texte_pdf(self, devis):
        import fitz
        from apps.ventes.quote_engine import (
            clean_pdf_options, generate_premium_devis_pdf,
        )
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as upload:
            generate_premium_devis_pdf(devis.id, clean_pdf_options({}),
                                       persist=False)
        doc = fitz.open(stream=upload.call_args[0][0], filetype='pdf')
        return _norm('\n'.join(p.get_text() for p in doc)), len(doc)

    def test_section_note_et_option_imprimees(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.montants import fmt_centimes
        devis = self._devis('DEV-QJR618-A')
        opt = build_quote_data(devis)['options_proposees'][0]
        # 1 000 HT + TVA 20 % = 1 200, remise globale 5 % = 1 140, puis
        # ARRONDI-100 (02/10/2026) : le TTC d'une option tombe au palier de
        # 100 inférieur — 1 100,00.
        self.assertEqual(opt['total_ttc'], 1100.0)
        texte, pages = self._texte_pdf(devis)
        # Rendu RÉSIDENTIEL premium (pas le repli legacy).
        self.assertIn('le détail de votre projet', texte)
        self.assertIn('section toiture qjr618', texte)
        self.assertIn('note visible pose sous quinze jours', texte)
        # Le libellé de bloc est en lettres espacées (letter-spacing) : PyMuPDF
        # l'extrait glyphe par glyphe (« o p t i o n s … ») — on compare donc
        # sans espaces, comme ``test_quote_engine_snapshot``.
        self.assertIn('optionsproposées', ''.join(texte.split()))
        self.assertIn('garantie étendue qjr618', texte)
        self.assertIn(_norm(fmt_centimes(opt['total_ttc'])), texte)
        self.assertEqual(pages, 3)

    def test_sans_structure_ni_option_rien_de_nouveau(self):
        devis = self._devis('DEV-QJR618-B', avec_structure=False)
        texte, pages = self._texte_pdf(devis)
        self.assertIn('le détail de votre projet', texte)
        self.assertNotIn('optionsproposées', ''.join(texte.split()))
        self.assertEqual(pages, 3)


#: QJR627 — l'étude minimale du marché industriel (même forme que QJR619).
ETUDE_INDUSTRIEL = {
    'kwc': 49.7, 'production_annuelle': 79520, 'conso_annuelle': 120000,
    'taux_autoconso': 92, 'taux_couverture': 61,
    'economies_annuelles': 98000, 'payback': 3.4, 'prix_kwc': 6100,
    'prod_mensuelle': [6627] * 12, 'conso_mensuelle': [10000] * 12,
}
NOTE = 'QA-AUDIT-3009 notes générales'


@tag('pdf')
class TestPdfNoteClient(TestCase):
    """QJR627 (D-QJR5-6) — le champ « Notes » du générateur est un texte
    CLIENT : imprimé dans le PDF (résidentiel, industriel, une page) ; vide →
    aucun bloc."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, ref, note, mode='residentiel', etude=None):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500', '10'),
            ('Onduleur réseau 5kW', '1', '9000', '20'),
        ], reference=ref, etude_params=etude)
        devis.note = note
        devis.mode_installation = mode
        devis.save(update_fields=['note', 'mode_installation'])
        return devis

    def _texte(self, devis, options=None):
        import fitz
        from apps.ventes.quote_engine import (
            clean_pdf_options, generate_premium_devis_pdf,
        )
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as upload:
            generate_premium_devis_pdf(devis.id, clean_pdf_options(options or {}),
                                       persist=False)
        doc = fitz.open(stream=upload.call_args[0][0], filetype='pdf')
        return _norm('\n'.join(p.get_text() for p in doc))

    def test_builder_expose_note_client(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-QJR627-D', f'  {NOTE}  ')
        self.assertEqual(build_quote_data(devis)['note_client'], NOTE)

    def test_residentiel_imprime_la_note(self):
        texte = self._texte(self._devis('DEV-QJR627-R', NOTE))
        self.assertIn('le détail de votre projet', texte)
        self.assertIn(_norm(NOTE), texte)

    def test_industriel_imprime_la_note(self):
        devis = self._devis('DEV-QJR627-I', NOTE, mode='industriel',
                            etude=dict(ETUDE_INDUSTRIEL))
        self.assertIn(_norm(NOTE), self._texte(devis))

    def test_une_page_imprime_la_note(self):
        devis = self._devis('DEV-QJR627-O', NOTE)
        self.assertIn(_norm(NOTE), self._texte(devis, {'pdf_mode': 'onepage'}))

    def test_note_vide_aucun_bloc(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-QJR627-V', '')
        self.assertEqual(build_quote_data(devis)['note_client'], '')
        texte = self._texte(devis)
        self.assertNotIn('qa-audit-3009', texte)
