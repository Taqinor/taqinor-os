"""QJR619 — le PDF commercial premium et la page 2 du format legacy complet
impriment sections, notes et options proposées.

``commercial/equip.py`` ne lisait que ``all_items`` ; ``equip_rows`` (page 2 du
legacy full + étude, 4 pages, et tout repli) ne lisait jamais
``LIGNES_STRUCTURE`` / ``OPTIONS_PROPOSEES`` — seul le une-page les imprimait.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_pdf_commercial_legacy_sections_options"
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

ETUDE = {
    'kwc': 49.7, 'production_annuelle': 79520, 'conso_annuelle': 120000,
    'taux_autoconso': 92, 'taux_couverture': 61,
    'economies_annuelles': 98000, 'payback': 3.4, 'prix_kwc': 6100,
    'prod_mensuelle': [6627] * 12, 'conso_mensuelle': [10000] * 12,
}


def _norm(texte):
    return re.sub(r'\s+', ' ', texte).strip().lower()


@tag('pdf')
class TestSectionsOptionsCommercialEtLegacy(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, ref, lignes, mode):
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference=ref, etude_params=dict(ETUDE))
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        LigneDevis.objects.filter(devis=devis).update(ordre=1)
        LigneDevis.objects.create(
            devis=devis, produit=None, designation='Section Toiture QJR619',
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne='section', ordre=0)
        LigneDevis.objects.create(
            devis=devis, produit=None, designation='Note visible QJR619',
            quantite=None, prix_unitaire=None, remise=Decimal('0'),
            taux_tva=None, type_ligne='note', ordre=2)
        produit = Produit.objects.create(
            company=self.company, nom='Monitoring QJR619', sku=f'{ref}-MON',
            prix_vente=Decimal('1000'), prix_achat=Decimal('7'),
            quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Monitoring QJR619',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'),
            optionnelle=True, ordre=3)
        return devis

    def _texte(self, devis, pdf_options):
        import fitz
        from apps.ventes.quote_engine import builder
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as up:
            builder.generate_premium_devis_pdf(devis.id,
                                               pdf_options=pdf_options)
        doc = fitz.open(stream=up.call_args[0][0], filetype='pdf')
        return _norm('\n'.join(p.get_text() for p in doc)), len(doc)

    def _assert_imprime(self, texte):
        self.assertIn('section toiture qjr619', texte)
        self.assertIn('note visible qjr619', texte)
        # Libellé en lettres espacées (letter-spacing) : PyMuPDF l'extrait
        # glyphe par glyphe — on compare donc sans espaces.
        self.assertIn('optionsproposées', ''.join(texte.split()))
        self.assertIn('monitoring qjr619', texte)

    def test_commercial_premium_full(self):
        from apps.ventes.quote_engine.commercial import renderer
        devis = self._devis('DEV-QJR619-COM', [
            ('Onduleur réseau Huawei 50kW', '1', '42000'),
            ('Panneau mono 710W', '70', '1150'),
        ], 'commercial')
        self.assertTrue(renderer.is_commercial(devis, {'pdf_mode': 'full'}))
        texte, pages = self._texte(devis, {'pdf_mode': 'full'})
        self._assert_imprime(texte)
        self.assertEqual(pages, 3)

    def test_residentiel_full_avec_etude_legacy(self):
        devis = self._devis('DEV-QJR619-RES', [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 5kW', '1', '9000'),
        ], 'residentiel')
        texte, pages = self._texte(
            devis, {'pdf_mode': 'full', 'include_etude': 1})
        self._assert_imprime(texte)
        self.assertEqual(pages, 4)
