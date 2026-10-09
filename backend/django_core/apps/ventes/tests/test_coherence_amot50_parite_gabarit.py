"""AMOT50 (C-AMOT-039) — la règle ``ETU_I8B_PARITE_GABARIT`` appelle le
GABARIT (HTML rendu sans réseau, ``render.build_html(renderer._augment(
data))``), relit ses chiffres par l'extracteur unique
``figures.extract_figures`` et les confronte au dict serveur : couverture,
−N %, économie, retour, TTC.

Moteur et gabarit réels. Test-du-test : une copie du gabarit qui imprime
``eco_a_ann`` à la place de ``eco_s_ann`` ⇒ violation
(``test_mauvaise_cle_detectee``) ; un gabarit qui lève ⇒ l'exception remonte
(``rule_errors`` nommée du moteur d'audit).
"""
from unittest import mock

from django.test import TestCase

from apps.ventes.coherence.moteur import _Ctx
from apps.ventes.coherence.registre import REGISTRE, charger_regles
from apps.ventes.coherence.regles_etude import ecarts_gabarit
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.quote_engine.residential import render as RD
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

# Ancrage RÉEL (12 factures) : sans lui la synthèse économies est omise du
# gabarit (Z2/M1) et la parité ne compare plus rien (faux vert).
_ANCRAGE = {'factures_mensuelles_reelles': [900, 850, 800, 750, 800, 950, 1100,
                                            1150, 1000, 850, 800, 900],
            'distributeur': 'onee', 'ville': 'casablanca'}

_LIGNES = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
    ('Onduleur hybride Deye 5kW', '1', '15000'),
    ('Batterie Dyness 5kWh', '1', '20000'),
]


class PariteGabaritTests(TestCase):
    def setUp(self):
        charger_regles()
        self.company = make_company(slug='amot50-co', nom='AMOT50')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), _LIGNES,
            reference='DEV-AMOT50-1',
            etude_params=dict(DEUX_OPTIONS, production_annuelle=9000,
                              economies_annuelles=12000, **_ANCRAGE))
        self.data = build_quote_data(self.devis,
                                     clean_pdf_options({'pdf_mode': 'full'}))

    def test_parite_sur_la_donnee_reelle(self):
        self.assertEqual(ecarts_gabarit(self.data), [])

    def test_mauvaise_cle_detectee(self):
        data = dict(self.data, roi_s=self.data['roi_s'] + 3)

        def gabarit_fautif(d):
            # Le gabarit imprime le retour SERVEUR d'origine pendant que le
            # dict en sert un autre : une clé mal lue.
            return RD.build_html(dict(d, roi_s=self.data['roi_s']))
        ecarts = ecarts_gabarit(data, build_html=gabarit_fautif)
        self.assertTrue(any('payback_ans' in e.identite for e in ecarts),
                        ecarts)

    def test_la_regle_appelle_le_gabarit(self):
        r = REGISTRE['ETU_I8B_PARITE_GABARIT']
        with mock.patch.object(RD, 'build_html',
                               side_effect=RuntimeError('gabarit appelé')):
            with self.assertRaisesMessage(RuntimeError, 'gabarit appelé'):
                r.check(r, self.devis, _Ctx(self.company))
