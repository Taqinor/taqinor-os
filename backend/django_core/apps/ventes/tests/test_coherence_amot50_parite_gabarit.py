"""AMOT50 (C-AMOT-039) — règle ``ETU_I8B_PARITE_GABARIT`` : sur la donnée
réelle, le HTML RENDU du gabarit résidentiel (sans réseau) est confronté au
dict serveur par ``figures.parite_gabarit`` (extracteur ``data-figure``
unique).

Rejoue VB (les 20 règles tournent sans jamais appeler le rendu).

Test-du-test : faire imprimer ``eco_a_ann`` à la place de ``eco_s_ann`` dans
une copie du gabarit ⇒ violation (``test_gabarit_qui_imprime_une_mauvaise_cle``).
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.coherence.registre import REGISTRE, charger_regles
from apps.ventes.quote_engine.figures import parite_gabarit
from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import _residential_sample_data


class _Ctx:
    def __init__(self, data):
        self._data = data

    def donnees_devis(self, devis, opts=None):
        return self._data


class PariteGabaritTests(SimpleTestCase):
    def setUp(self):
        charger_regles()
        self.data = _residential_sample_data()

    def _html(self, data):
        return render.build_html(renderer._augment(dict(data)))

    def test_gabarit_concorde_avec_le_serveur(self):
        self.assertEqual(parite_gabarit(self.data, self._html(self.data)), [])

    def test_gabarit_qui_imprime_une_mauvaise_cle(self):
        faux = dict(self.data, eco_s_ann=self.data['eco_s_ann'] + 5000)
        ecarts = parite_gabarit(self.data, self._html(faux))
        self.assertTrue(ecarts)

    def test_regle_appelle_le_gabarit(self):
        regle = REGISTRE['ETU_I8B_PARITE_GABARIT']
        devis = SimpleNamespace(pk=1, reference='DEV-AMOT50', company_id=1)
        with mock.patch('apps.ventes.coherence.regles_etude._residentiel',
                        return_value=True), \
                mock.patch.object(render, 'build_html',
                                  side_effect=RuntimeError('gabarit')):
            with self.assertRaises(RuntimeError):
                regle.check(regle, devis, _Ctx(self.data))

    def test_regle_signale_l_ecart(self):
        regle = REGISTRE['ETU_I8B_PARITE_GABARIT']
        devis = SimpleNamespace(pk=1, reference='DEV-AMOT50', company_id=1)
        faux = dict(self.data, eco_s_ann=self.data['eco_s_ann'] + 5000)
        html_faux = self._html(faux)
        with mock.patch('apps.ventes.coherence.regles_etude._residentiel',
                        return_value=True), \
                mock.patch.object(render, 'build_html',
                                  return_value=html_faux):
            violations = regle.check(regle, devis, _Ctx(self.data))
        self.assertTrue(violations)
