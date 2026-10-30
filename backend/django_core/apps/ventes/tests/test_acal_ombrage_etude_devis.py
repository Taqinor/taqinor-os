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
        # ACAL137 — l'accès solaire vit DANS LA GÉOMÉTRIE DE CHAQUE PAN
        # (forme du contrat roof_layout_v2 : valeurs par module + méthode
        # objet), jamais à la racine : l'étape « accès module » s'applique
        # et la perte d'ombrage de chaque pan est MESURÉE.
        for zone in layout['zones']:
            zone['geometry']['solarAccess'] = {
                'values': [0.9] * zone['geometry']['count'],
                'method': {'horizon': False, 'rangees': False,
                           'resolution': 'annuelle',
                           'description': 'Accès solaire annuel'},
                'assumptions': {'periode': 'annee'},
                'computedAt': '2026-10-01T10:00:00Z',
            }
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

    # ── D-RES-2710-1 (fondateur, 27/10/2026) — le moteur horaire résidentiel
    # retire la perte d'ombrage SERVIE par le calepinage, niveau de règles 3.

    def _kwargs_horaire(self):
        from apps.ventes.horaire.conso import profil_depuis_factures
        conso, _source, _detail = profil_depuis_factures(
            facture_hiver_mad=1200)
        return {'kwc': 5.0, 'conso_kwh_mensuelles': conso,
                'ville': 'Casablanca', 'tranches': None,
                'charges_fixes_mad': None}

    def test_d_res_2710_1_moteur_horaire_retire_l_ombrage_servi(self, *_m):
        from apps.ventes.etude_horaire import calculer_etude_horaire
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)
            perte = perte_ombrage_du_devis(self.devis)
        self.assertGreater(perte, 0.0)
        self.assertAlmostEqual(perte, float(servi['global']), places=6)
        kwargs = self._kwargs_horaire()
        brut = calculer_etude_horaire(**kwargs)['annuel']['production_kwh']
        ombre = calculer_etude_horaire(
            perte_ombrage_pct=perte, **kwargs)['annuel']['production_kwh']
        self.assertAlmostEqual(ombre / brut, 1.0 - perte / 100.0, places=3)

    def test_d_res_2710_1_devis_envoye_niveau_2_garde_sa_production(self, *_m):
        from apps.ventes.horaire.ombrage import (
            facteur_production_saison, perte_ombrage_du_devis)
        Devis.objects.filter(pk=self.devis.pk).update(regles_calcul=2)
        self.devis.refresh_from_db()
        with patch_materiel():
            self.assertIsNone(perte_ombrage_du_devis(self.devis))
            self.assertEqual(facteur_production_saison(self.devis), 1.0)

    def test_d_res_2710_1_simulation_perimee_aucun_ombrage(self, *_m):
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=layout)
        with patch_materiel():
            self.assertIsNone(perte_ombrage_du_devis(self.devis))

    def test_c_rhor_004_courbe_saison_au_derate_du_devis(self, *_m):
        from apps.ventes.horaire.ombrage import (
            facteur_production_saison, perte_ombrage_du_devis)
        from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
        with patch_materiel():
            perte = perte_ombrage_du_devis(self.devis)
            facteur = facteur_production_saison(self.devis)
        self.assertAlmostEqual(
            facteur, PRODUCTION_DERATE * (1.0 - perte / 100.0), places=9)

    def test_err_rhor8_balayage_du_stockage_ombre_comme_l_etude(self, *_m):
        """ERR-RHOR8-TAILLES-PRODUCTION-SANS-OMBRAGE (devis 2007 : carte Max
        9 084 kWh non ombrée vs 8 473 officiels) — ``balayer_stockage_horaire``
        accepte ``perte_ombrage_pct`` : ``kwargs_ombrage`` ne rend plus ``{}``,
        et le balayage (cartes de tailles, échelle de paliers) produit ce que
        produit l'étude ombrée à kWc égal. Test-du-test : retirer le paramètre
        du balayage ⇒ ``kwargs_ombrage`` rend ``{}``, rouge."""
        from apps.ventes.domain.entrees import kwargs_ombrage
        from apps.ventes.etude_horaire import (
            balayer_stockage_horaire, calculer_etude_horaire)
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        with patch_materiel():
            perte = perte_ombrage_du_devis(self.devis)
        self.assertGreater(perte, 0.0)
        ombre = kwargs_ombrage(perte, calculer_etude_horaire,
                               balayer_stockage_horaire)
        self.assertEqual(ombre, {'perte_ombrage_pct': perte})
        kwargs = self._kwargs_horaire()
        brut = balayer_stockage_horaire(capacites_kwh=[5.0], **kwargs)
        balaye = balayer_stockage_horaire(capacites_kwh=[5.0], **ombre, **kwargs)
        etude = calculer_etude_horaire(**ombre, **kwargs)
        self.assertAlmostEqual(
            balaye['production_annuelle_kwh'] / brut['production_annuelle_kwh'],
            1.0 - perte / 100.0, places=3)
        self.assertAlmostEqual(balaye['production_annuelle_kwh'],
                               etude['annuel']['production_kwh'], delta=1.0)
