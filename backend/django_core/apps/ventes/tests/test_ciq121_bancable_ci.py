"""CIQ121 — étude bancable d'un devis C&I : la charge vient de l'étude C&I
(jours types du profil déclaré), jamais du profil « commercial » codé ; aucune
économie de prime fixe / puissance souscrite attribuée au PV seul.

Fetchers réseau monkeypatchés (patron PV72) : aucun accès réseau.
"""
from unittest import mock

from django.test import TestCase

from apps.ventes.etude import (
    MENTION_PUISSANCE_SOUSCRITE,
    MOTIF_SANS_ETUDE_CI,
    _courbe_ci_depuis_etude,
    run_bankable_study,
)
from apps.ventes.tests.test_pv72_full_chain import _fake_productible, _fake_tmy
from apps.ventes.tests.test_quote_engine import (
    make_client, make_company, make_devis, make_user,
)

#: Deux jours types (janvier ouvré, janvier fermé) — 24 h chacun.
JOURS_TYPES = [
    {'mois': 1, 'type_jour': 'ouvre', 'nb_jours': 22,
     'charge_kwh': [2.0] * 7 + [12.0] * 11 + [2.0] * 6},
    {'mois': 1, 'type_jour': 'ferme', 'nb_jours': 9, 'charge_kwh': [2.0] * 24},
] + [{'mois': m, 'type_jour': 'ouvre', 'nb_jours': 30,
      'charge_kwh': [3.0] * 7 + [10.0] * 11 + [3.0] * 6} for m in range(2, 13)]


def _energie(jours_types):
    return sum(j['nb_jours'] * sum(j['charge_kwh']) for j in jours_types)


@mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
@mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)
class BancableCITests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, reference, **fields):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '40', '1500'),
            ('Onduleur réseau 20kW', '1', '20000'),
        ], reference=reference)
        for k, v in fields.items():
            setattr(devis, k, v)
        devis.save()
        return devis

    def _zone(self):
        return {'label': 'Toiture', 'lat': 33.57, 'lon': -7.59,
                'tilt': 10, 'azimuth': 0, 'kwc': 18.0}

    def test_courbe_deroulee_meme_energie(self, _p, _t):
        devis = self._devis('DEV-CIQ121-1', mode_installation='industriel',
                            etude_params={'etude_ci': {'profil_charge': {
                                'jours_types': JOURS_TYPES}}})
        courbe = _courbe_ci_depuis_etude(devis)
        self.assertEqual(len(courbe), 288)
        self.assertAlmostEqual(sum(courbe), _energie(JOURS_TYPES), places=6)

    def test_bancable_industriel_charge_de_l_etude_ci(self, _p, _t):
        devis = self._devis('DEV-CIQ121-2', mode_installation='industriel',
                            etude_params={'etude_ci': {'profil_charge': {
                                'jours_types': JOURS_TYPES}}})
        res = run_bankable_study(devis, zones=[self._zone()])
        sc = res['self_consumption']
        self.assertIsNotNone(sc['self_consumed_kwh'])
        conso = sc['self_consumed_kwh'] + sc['grid_import_kwh']
        self.assertAlmostEqual(conso, _energie(JOURS_TYPES), delta=1.0)
        self.assertNotIn(MOTIF_SANS_ETUDE_CI, res['warnings'])

    def test_sans_etude_ci_autoconsommation_omise(self, _p, _t):
        devis = self._devis('DEV-CIQ121-3', mode_installation='commercial',
                            etude_params={})
        res = run_bankable_study(devis, zones=[self._zone()])
        self.assertIsNone(res['self_consumption']['self_consumed_kwh'])
        self.assertIsNone(res['self_consumption']['self_consumption_rate'])
        self.assertIn(MOTIF_SANS_ETUDE_CI, res['warnings'])

    def test_annual_saving_null_en_ci(self, _p, _t):
        devis = self._devis('DEV-CIQ121-4', mode_installation='industriel',
                            etude_params={'puissance_souscrite_kva': 80,
                                          'etude_ci': {'profil_charge': {
                                              'jours_types': JOURS_TYPES}}})
        sp = run_bankable_study(devis, zones=[self._zone()])['subscribed_power']
        self.assertIsNone(sp['annual_saving'])
        self.assertEqual(sp['mention'], MENTION_PUISSANCE_SOUSCRITE)

    def test_residentiel_inchange(self, _p, _t):
        devis = self._devis('DEV-CIQ121-5', mode_installation='residentiel')
        res = run_bankable_study(devis, zones=[self._zone()])
        self.assertIsNone(res['subscribed_power']['annual_saving'])
        self.assertIsNone(res['subscribed_power']['mention'])
        self.assertNotIn(MOTIF_SANS_ETUDE_CI, res['warnings'])
        self.assertIsNotNone(res['self_consumption']['self_consumed_kwh'])
