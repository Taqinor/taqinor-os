"""ACAL144 (C-ACAL-075/078) — l'étude bancable du devis lit l'ombrage du
calepinage par ``ombrage_servi``, ZONE PAR ZONE, et retombe sur son chemin
quand il est PÉRIMÉ (fin de la tautologie).

Calepinage RÉEL simulé par la vraie chaîne (client météo rejoué, fiches
matériel injectées comme dans les tests du module), sélecteur JAMAIS mocké ;
seuls les deux fetchers réseau de l'étude (PVGIS productible / TMY) sont
rejoués, comme dans PV69/PV70.

Run :
    python manage.py test apps.ventes.tests.test_acal_ombrage_etude_devis -v2
"""
import copy
from unittest import mock

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.selectors import ombrage_servi
from apps.calepinage.services.liens import lier_devis
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.tests.acal_livrables_helpers import patch_materiel
from apps.calepinage.tests.test_acal_multi_pans import (
    _ClientParOrientation, _layout, _zone,
)
from apps.calepinage.tests.test_api_liste import BaseApiCalepinage
from apps.calepinage.tests.test_calx5_simulation import MATERIEL
from apps.ventes.etude import (
    AVERTISSEMENT_OMBRAGE_PERIME, ORIGINE_OMBRAGE_CALEPINAGE,
    ORIGINE_OMBRAGE_ETUDE, run_bankable_study,
)
from apps.ventes.models import Devis


def _fake_productible(settings, lat, lon, *, peakpower_kwc=1.0, tilt=None,
                      azimuth=None):
    return {'source': 'pvgis', 'productible_kwh_kwc': 1700.0,
            'production_mensuelle_kwh_kwc': None, 'reason': None}


def _fake_tmy(lat, lon, **_kwargs):
    return {'source': 'pvgis', 'irradiance_annuelle_kwh_m2': 2000.0,
            'irradiance_mensuelle_kwh_m2': [120.0] * 12,
            'temperature_moyenne_c': 19.0, 'reason': None}


_PATCH_TMY = mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
                        side_effect=_fake_tmy)
_PATCH_PROD = mock.patch('apps.parametres.pvgis.fetch_productible',
                         side_effect=_fake_productible)

ZONES = [
    {'label': 'PAN-1', 'lat': 33.5731, 'lon': -7.5898, 'tilt': 15,
     'azimuth': 90, 'kwc': 8.8},
    {'label': 'PAN-2', 'lat': 33.5731, 'lon': -7.5898, 'tilt': 15,
     'azimuth': 270, 'kwc': 4.4},
]


@_PATCH_TMY
@_PATCH_PROD
class OmbrageEtudeDevisTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-1441')
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        layout['solarAccess'] = {'values': [0.9] * 24}
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Ombrage 144',
            roof_layout=layout)
        lier_devis(self.calepinage, self.devis.pk)
        with patch_materiel():
            simuler_calepinage(self.calepinage,
                               client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True)
        self.calepinage.refresh_from_db()
        self.devis.refresh_from_db()

    def _etude(self):
        with patch_materiel():
            return run_bankable_study(self.devis, zones=copy.deepcopy(ZONES))

    def test_calepinage_retouche_sans_simulation_repli_etude(self, *_m):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        layout['zones'][0]['obstacles'] = [{'id': 'o1', 'heightM': 2.0}]
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        etude = self._etude()
        self.assertEqual(etude['origine_ombrage'], ORIGINE_OMBRAGE_ETUDE)
        self.assertIn(AVERTISSEMENT_OMBRAGE_PERIME, etude['warnings'])

    def test_ombrage_par_zone(self, *_m):
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)
        self.assertFalse(servi['perime'])
        etude = self._etude()
        self.assertEqual(etude['origine_ombrage'], ORIGINE_OMBRAGE_CALEPINAGE)
        par_zone = {z['label']: z['shading_annual_loss_pct']
                    for z in etude['zones']}
        for label in ('PAN-1', 'PAN-2'):
            self.assertAlmostEqual(par_zone[label],
                                   float(servi['par_pan'][label]), places=2)
        if servi['par_pan']['PAN-1'] != servi['par_pan']['PAN-2']:
            self.assertNotEqual(par_zone['PAN-1'], par_zone['PAN-2'])

    def test_aucune_condition_de_variante_retenue(self, *_m):
        # Aucune variante n'existe : l'ombrage du calepinage est LU quand même.
        self.assertFalse(CalepinageVariante.objects.filter(
            calepinage=self.calepinage).exists())
        etude = self._etude()
        self.assertEqual(etude['origine_ombrage'], ORIGINE_OMBRAGE_CALEPINAGE)
        # Relancer deux fois sans changement ⇒ identique.
        self.assertEqual(
            [z['shading_annual_loss_pct'] for z in etude['zones']],
            [z['shading_annual_loss_pct'] for z in self._etude()['zones']])
