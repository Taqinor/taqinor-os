"""ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — une installation dont le cumul
25 ans ne croise JAMAIS zéro n'est plus imprimée « Rentabilisé en 25 ans ».

``pricing.compute_cashflow_payback`` rendait la sentinelle ``25.0`` sans rien
dire ; le résidentiel l'imprimait (carte page 1, point + étiquette sur la
courbe, comparatif, gain net planché à « ≈ 0 MAD »). Le drapeau
``jamais_rembourse`` (→ ``roi_s_jamais``/``roi_a_jamais``) pilote désormais le
rendu : « Non rentabilisé sur 25 ans », aucun nombre d'années, aucun point.

Aucune base : fixtures PURES ``_moteur_fixtures`` (HTML exact des gabarits).

Run : ``python manage.py test apps.ventes.tests.test_err_payback_jamais_rembourse``
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine.pricing import compute_cashflow_payback
from apps.ventes.tests._moteur_fixtures import html_legacy, html_residentiel


class DrapeauCashflowTests(SimpleTestCase):

    def test_jamais_rembourse_drapeau_vrai(self):
        # DEV-202609-0060 : 269 065 TTC pour ~3 000 MAD/an d'économie.
        cf = compute_cashflow_payback(269065, 3000)
        self.assertTrue(cf['jamais_rembourse'])
        self.assertLess(cf['cumulative'][-1], 0)
        # La sentinelle numérique reste (comparaisons des appelants).
        self.assertEqual(cf['payback_years'], 25.0)

    def test_rembourse_drapeau_faux(self):
        cf = compute_cashflow_payback(50000, 8000)
        self.assertFalse(cf['jamais_rembourse'])
        self.assertLess(cf['payback_years'], 25)

    def test_sans_economie_drapeau_faux(self):
        self.assertFalse(compute_cashflow_payback(50000, 0)['jamais_rembourse'])


class RenduResidentielTests(SimpleTestCase):

    def test_deux_options_jamais_remboursees(self):
        h = html_residentiel('deux', roi_s=25.0, roi_a=25.0,
                             roi_s_jamais=True, roi_a_jamais=True)
        self.assertIn('Non rentabilisé sur 25 ans', h)
        self.assertNotIn('Rentabilisé en', h)
        self.assertNotIn('data-figure="payback_ans"', h)
        # Le gain net n'est plus un « ≈ 0 MAD » planché.
        self.assertIn('p2-stat-v">Non rentabilisé', h)

    def test_une_option_jamais_remboursee(self):
        h = html_residentiel('deux', roi_a=25.0, roi_a_jamais=True)
        self.assertIn('Non rentabilisé sur 25 ans', h)
        self.assertEqual(
            len(re.findall(r'data-figure="payback_ans"', h)), 1,
            'seule l’option remboursée garde son marqueur de payback')

    def test_temoin_sans_drapeau_inchange(self):
        h = html_residentiel('deux')
        self.assertIn('Rentabilisé en', h)
        self.assertNotIn('Non rentabilisé', h)


class RenduLegacyTests(SimpleTestCase):

    def test_pastille_legacy(self):
        h = html_legacy('deux', roi_s=25.0, roi_a=25.0,
                        roi_s_jamais=True, roi_a_jamais=True)
        self.assertIn('Non rentabilisé sur 25 ans', h)
        self.assertNotIn('Retour en 25', h)
