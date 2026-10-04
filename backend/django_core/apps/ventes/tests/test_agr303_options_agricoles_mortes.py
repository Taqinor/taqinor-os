"""AGR303 — les options PDF agricoles mortes sont retirées, et un paramètre
de rendu ne surcharge plus l'énergie actuelle déclarée dans l'étude.

Avant : ``DEFAULT_PDF_OPTIONS`` déclarait cinq bascules « de persuasion »
(aide FDA 30 % active par défaut, comparatif carburant, environnement,
schéma, eau livrée) qu'AUCUN renderer ne lisait depuis QJR236/DV1, et
l'option ``current_fuel`` d'un appel de rendu ÉCRASAIT ``etude['current_fuel']``
— un paramètre de requête modifiait une donnée client (contraire à D-AGR-5).
"""
from django.test import SimpleTestCase, TestCase

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

CLES_MORTES = (
    'show_subsidy', 'show_fuel_comparison', 'show_environmental',
    'show_schematic', 'show_water_yield', 'current_fuel',
)


class Agr303CleanPdfOptionsTests(SimpleTestCase):

    def test_les_options_mortes_ne_sont_plus_rendues(self):
        from apps.ventes.quote_engine.builder import clean_pdf_options
        opts = clean_pdf_options({'show_subsidy': True,
                                  'current_fuel': 'diesel'})
        for cle in CLES_MORTES:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, opts)

    def test_aucune_option_morte_dans_les_defauts(self):
        from apps.ventes.quote_engine.builder import DEFAULT_PDF_OPTIONS
        for cle in CLES_MORTES:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, DEFAULT_PDF_OPTIONS)

    def test_aucune_option_ne_pilote_un_montant_d_aide(self):
        """Q22 / D-AGR-6 : aucune option de rendu ne nomme une aide."""
        from apps.ventes.quote_engine.builder import DEFAULT_PDF_OPTIONS
        for cle in DEFAULT_PDF_OPTIONS:
            with self.subTest(cle=cle):
                self.assertNotIn('subsid', cle)
                self.assertNotIn('fda', cle.lower())


class Agr303EtudeJamaisSurchargeeTests(TestCase):

    ETUDE = {
        'pompe_cv': '5.5', 'pompe_kw': 4.05, 'type_pompe': 'immergee',
        'alim': 'tri', 'hmt_m': '80', 'champ_kwc': 5.68,
    }

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            [('Pompe immergée 5,5 CV', '1', '18000'),
             ('Panneau mono 550W', '12', '1100')],
            reference='DEV-AGR303-AGRI', etude_params=dict(self.ETUDE))
        self.devis.mode_installation = 'agricole'
        self.devis.save(update_fields=['mode_installation'])

    def test_l_option_current_fuel_ne_modifie_pas_l_etude_rendue(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self.devis.refresh_from_db()
        stockee = dict(self.devis.etude_params or {})
        data = build_quote_data(
            self.devis, {'pdf_mode': 'full', 'current_fuel': 'diesel'})
        self.assertEqual(data['etude'].get('current_fuel'),
                         stockee.get('current_fuel'))
        for cle, valeur in stockee.items():
            with self.subTest(cle=cle):
                self.assertEqual(data['etude'].get(cle), valeur)

    def test_la_charge_utile_ne_porte_plus_les_bascules_mortes(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(self.devis, {'pdf_mode': 'full'})
        for cle in CLES_MORTES:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, data)
