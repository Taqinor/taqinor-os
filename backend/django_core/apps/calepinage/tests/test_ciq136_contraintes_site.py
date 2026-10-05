"""CIQ136 — contraintes de site saisies PAR PROJET (assureur, incendie),
jamais imposées par défaut.

* projet FM ⇒ lanterneau à 1,8 m DANS LE MOTEUR, règle citant DS 1-15 ;
* projet sans assureur ⇒ dégagements d'aujourd'hui au centimètre ;
* saisie sans source ⇒ 400 FR ; préréglage FM seulement pour FM ;
* migration réversible ; scoping société.
"""
import math
from importlib import import_module

from django.db import migrations
from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.degagements import (
    PRESET_FM_DS_1_15, ContraintesSiteInvalides, degagement_effectif,
    normaliser_contraintes_site,
)
from apps.calepinage.services.traduction import entree_depuis_layout

from .test_api_liste import BaseApiCalepinage, url_detail


def _rectangle(lon0, lat0, largeur_m, hauteur_m):
    dlon = largeur_m / (111320.0 * math.cos(math.radians(lat0))) / 2.0
    dlat = hauteur_m / 110540.0 / 2.0
    return [[lon0 - dlon, lat0 - dlat], [lon0 + dlon, lat0 - dlat],
            [lon0 + dlon, lat0 + dlat], [lon0 - dlon, lat0 + dlat]]


def _document(type_obstacle):
    return {
        'version': 2, 'pin': {'lat': 33.5, 'lng': -7.6}, 'panelWatt': 720,
        'panelLengthM': 2.278, 'panelWidthM': 1.134, 'activeAreaId': 'z1',
        'zones': [{
            'id': 'z1', 'label': 'Toit', 'roofType': 'flat',
            'vertices': _rectangle(-7.6, 33.5, 40.0, 30.0),
            'obstacles': [{'id': 'obs-1', 'centerLng': -7.6,
                           'centerLat': 33.5, 'lengthM': 1.2, 'widthM': 1.2,
                           'type': type_obstacle, 'provenance': 'MESURE'}],
        }],
    }


class ContraintesMoteurTests(SimpleTestCase):
    def _obstacle(self, type_obstacle, contraintes):
        traduction = entree_depuis_layout(_document(type_obstacle),
                                          contraintes_site=contraintes)
        return traduction.document['obstacles'][0]

    def test_projet_fm_lanterneau_a_1_8_m_regle_ds_1_15(self):
        contraintes = normaliser_contraintes_site({'assureur': 'fm_global'})
        obstacle = self._obstacle('lanterneau', contraintes)
        self.assertAlmostEqual(obstacle['degagement_m'], 1.8)
        self.assertIn('DS 1-15', obstacle['regle_appliquee'])

    def test_sans_assureur_chiffres_d_aujourd_hui(self):
        for type_obstacle in ('cheminee', 'antenne', 'lanterneau'):
            avant = self._obstacle(type_obstacle, None)
            apres = self._obstacle(type_obstacle,
                                   normaliser_contraintes_site({}))
            self.assertEqual(avant['degagement_m'], apres['degagement_m'])
            self.assertEqual(avant['regle_appliquee'],
                             apres['regle_appliquee'])

    def test_effectif_est_le_maximum(self):
        valeur, _ = degagement_effectif('cheminee', None, {
            'degagements_m': {'lanterneau': 1.8}})
        self.assertEqual(valeur, 0.50)  # le projet ne vise pas les cheminées


class NormalisationTests(SimpleTestCase):
    def test_vide_par_defaut(self):
        self.assertEqual(normaliser_contraintes_site(None), {})
        self.assertEqual(normaliser_contraintes_site({'assureur': 'aucun'}),
                         {})

    def test_preset_seulement_pour_fm(self):
        fm = normaliser_contraintes_site({'assureur': 'fm_global'})
        self.assertEqual(fm['degagements_m'],
                         PRESET_FM_DS_1_15['degagements_m'])
        self.assertIn('§2.1.1.4', fm['source']['reference'])
        apsad = normaliser_contraintes_site({'assureur': 'apsad'})
        self.assertEqual(apsad['degagements_m'], {})
        self.assertIsNone(apsad['ilot_max_m'])

    def test_valeur_sans_source_refusee(self):
        with self.assertRaises(ContraintesSiteInvalides):
            normaliser_contraintes_site({
                'assureur': 'apsad', 'degagements_m': {'lanterneau': 1.0}})

    def test_migration_reversible(self):
        module = import_module(
            'apps.calepinage.migrations.0018_ciq136_contraintes_site')
        ops = module.Migration.operations
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], migrations.AddField)
        self.assertTrue(ops[0].reversible)


class ContraintesApiTests(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.cal = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Usine')

    def test_saisie_sans_source_400_fr(self):
        r = self.api.patch(url_detail(self.cal.pk), {'contraintes_site': {
            'assureur': 'autre', 'degagements_m': {'rive': 1.0}}},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('contraintes_site', r.data)
        self.assertIn('source', str(r.data['contraintes_site']))

    def test_fm_charge_le_preset_et_detail_l_expose(self):
        r = self.api.patch(url_detail(self.cal.pk), {
            'contraintes_site': {'assureur': 'fm_global'}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        detail = self.api.get(url_detail(self.cal.pk)).data
        self.assertEqual(detail['contraintes_site']['degagements_m'][
            'lanterneau'], 1.8)

    def test_scoping_societe(self):
        r = self.api_autre.patch(url_detail(self.cal.pk), {
            'contraintes_site': {'assureur': 'fm_global'}}, format='json')
        self.assertEqual(r.status_code, 404)
        self.cal.refresh_from_db()
        self.assertEqual(self.cal.contraintes_site, {})
