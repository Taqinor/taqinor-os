"""AMOT33 (C-AMOT-043) — le gabarit résidentiel suit l'option RECOMMANDÉE par
le serveur (``data['recommended']``) : badge, phrase « Pourquoi nous la
recommandons », pastille page 3, légende et chiffres vedettes ; aucun badge
quand il n'y a pas de recommandation.

Moteur réel (``build_quote_data``) puis rendu résidentiel réel
(``renderer._augment`` → ``render.build_html``). Test-du-test : remettre
``recommended=True`` littéral sur la chaîne de l'option 2 (``options.py``) et
``reco=True`` sur sa carte ⇒ ``test_recommande_sans`` échoue.
"""
import html as _html

from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.quote_engine.figures import (
    option_economique, option_recommandee,
)
from apps.ventes.quote_engine.residential import render as res_render
from apps.ventes.quote_engine.residential import renderer as res_renderer
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

_LIGNES = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
    ('Onduleur hybride Deye 5kW', '1', '15000'),
    ('Batterie Dyness 5kWh', '1', '20000'),
]
_PILL = 'c1-reco-pill">Recommandé'
_MINI = 'p3-reco-mini">recommandé'


class RecommandeTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot33-co', nom='AMOT33')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _data(self, reco):
        self.n += 1
        # Devis ANCRÉ sur 12 factures réelles (patron
        # ``test_adev50_cumul_25_ans_servi``) : sans série de factures, la
        # synthèse résidentielle vaut None et ``renderer._augment`` lève
        # ``masquer_synthese`` (Z2/M1 : ``not factures_reelles``) — la couche
        # économique, dont le gain net 25 ans et son libellé d'option, est
        # alors omise et les « chiffres vedettes » ne seraient pas testés.
        # Une consommation annuelle seule ne suffit pas.
        etude = dict(DEUX_OPTIONS, factures_mensuelles_reelles=[1800] * 12,
                     distributeur='onee', ville='casablanca')
        if reco:
            etude['recommended_option'] = reco
        devis = make_devis(self.company, self.user, self.client_obj, _LIGNES,
                           reference=f'DEV-AMOT33-{self.n}',
                           etude_params=etude)
        return build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))

    @staticmethod
    def _html(data):
        return _html.unescape(res_render.build_html(
            res_renderer._augment(dict(data))))

    def test_recommande_sans(self):
        data = self._data('Sans batterie')
        self.assertEqual(data['recommended'], 'Sans batterie')
        self.assertEqual(option_recommandee(data), 'sans')
        self.assertEqual(option_economique(
            {k: v for k, v in data.items() if k != 'eco_option'}), 'sans')
        h = self._html(data)
        self.assertEqual(h.count(_PILL), 1)
        self.assertLess(h.index(_PILL), h.index('Option 2'))
        self.assertIn("Pourquoi nous la recommandons : l'investissement", h)
        self.assertNotIn('vos soirées et les coupures passent sur batterie',
                         h)
        self.assertIn('option sans batterie', h)
        self.assertEqual(h.count(_MINI), 1)
        accord = h[h.index('Cochez votre option'):]
        self.assertLess(accord.index(_MINI), accord.rindex('p3-box'))

    def test_recommande_avec_inchange(self):
        data = self._data('Avec batterie')
        h = self._html(data)
        self.assertEqual(h.count(_PILL), 1)
        self.assertGreater(h.index(_PILL), h.index('Option 2'))
        self.assertIn('vos soirées et les coupures passent sur batterie', h)

    def test_aucune_recommandation(self):
        data = dict(self._data('Avec batterie'),
                    recommended='Aucune recommandation')
        self.assertIsNone(option_recommandee(data))
        h = self._html(data)
        self.assertNotIn(_PILL, h)
        self.assertNotIn(_MINI, h)
        self.assertNotIn('Pourquoi nous la recommandons', h)
