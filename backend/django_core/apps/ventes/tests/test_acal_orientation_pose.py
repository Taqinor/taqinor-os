"""ACAL58 — l'orientation POSÉE des modules avant la pente du toit.

Constat C-ACAL-022 (C1, S1) : un toit PLAT (``pitchDeg: 0``) portant des
tables inclinées à 10° partait à PVGIS à 0° — ``extract_roof_config`` ne
lisait que la pente du TOIT. ``orientation_du_pan`` (ventes/domain/geometrie.py)
lit désormais ``geometry.tiltDeg``/``azimuthDeg`` d'abord ; sans ``geometry``,
la lecture du toit est inchangée au bit près ; une pose est-ouest garde la
lecture actuelle (C-ACAL-081, non tranchée ici).

Run :
    python manage.py test apps.ventes.tests.test_acal_orientation_pose -v2
"""
import copy
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.ventes.calepinage_options import _pan_principal
from apps.ventes.domain.creation import _calepinage_range
from apps.ventes.models import Devis
from apps.ventes.services import extract_roof_config, orientation_du_pan
from apps.ventes.tasks import zones_etude_du_devis
from authentication.models import Company


def _zone_plate_inclinee(**geo):
    geometrie = {'tiltDeg': 10, 'azimuthDeg': 180, 'family': 'south',
                 'count': 12, 'kwc': 7.44}
    geometrie.update(geo)
    return {'label': 'Toit plat', 'roofType': 'flat', 'pitchDeg': 0,
            'facingAzimuthDeg': None, 'geometry': geometrie}


def _layout(zone):
    return {'version': 1, 'pin': {'lat': 33.57, 'lng': -7.59},
            'zones': [zone]}


class OrientationPoseeTest(SimpleTestCase):
    def test_toit_plat_incline_10_part_a_10(self):
        cfg = extract_roof_config(_layout(_zone_plate_inclinee()))
        pan = cfg['pans'][0]
        self.assertEqual(pan['inclinaison_deg'], 10)
        self.assertEqual(pan['azimut_deg'], 180)       # boussole (F3)
        self.assertEqual(pan['orientation'], 'Sud')
        self.assertEqual(pan['source_orientation'], 'pose')
        self.assertEqual(cfg['inclinaison_deg'], 10)
        self.assertEqual(cfg['azimut_deg'], 180)

    def test_zone_sans_geometry_garde_le_toit_au_bit_pres(self):
        zone = {'label': 'Pan', 'roofType': 'pitched', 'pitchDeg': 30,
                'facingAzimuthDeg': 135,
                'result': {'count': 10, 'kwc': 5.5, 'areaM2': 20}}
        pan = extract_roof_config(_layout(zone))['pans'][0]
        self.assertEqual(pan['inclinaison_deg'], 30)
        self.assertEqual(pan['azimut_deg'], 135)
        self.assertEqual(pan['orientation'], 'Sud-Est')
        self.assertEqual(pan['source_orientation'], 'toit')
        # Repli ``aspect`` (PVGIS) et ``pitch`` : inchangés eux aussi.
        zone2 = {'pitch': 12, 'aspect': 0,
                 'result': {'count': 4, 'kwc': 2.0}}
        pan2 = extract_roof_config(_layout(zone2))['pans'][0]
        self.assertEqual(pan2['inclinaison_deg'], 12)
        self.assertEqual(pan2['azimut_deg'], 180.0)
        self.assertEqual(pan2['source_orientation'], 'toit')

    def test_geometry_sans_angles_garde_le_toit(self):
        zone = _zone_plate_inclinee()
        zone['geometry'] = {'count': 12, 'kwc': 7.44, 'family': 'south'}
        zone['pitchDeg'] = 5
        zone['facingAzimuthDeg'] = 170
        o = orientation_du_pan(zone)
        self.assertEqual((o['inclinaison_deg'], o['azimut_deg'],
                          o['source_orientation']), (5, 170, 'toit'))

    def test_eastwest_garde_la_lecture_actuelle(self):
        """C-ACAL-081 non tranchée : une pose est-ouest lit le TOIT (figé)."""
        zone = _zone_plate_inclinee(family='eastwest', azimuthDeg=90,
                                    tiltDeg=10)
        zone['facingAzimuthDeg'] = 180
        pan = extract_roof_config(_layout(zone))['pans'][0]
        self.assertEqual(pan['inclinaison_deg'], 0)
        self.assertEqual(pan['azimut_deg'], 180)
        self.assertEqual(pan['source_orientation'], 'toit')

    def test_resynchroniser_deux_fois_meme_geometrie(self):
        layout = _layout(_zone_plate_inclinee())
        premier = extract_roof_config(copy.deepcopy(layout))
        second = extract_roof_config(copy.deepcopy(layout))
        self.assertEqual(premier, second)

    def test_annexe_client_branche_zones_lit_la_pose(self):
        pan = _pan_principal({'zones': [_zone_plate_inclinee()]})
        self.assertEqual(pan['inclinaison_deg'], 10)
        self.assertEqual(pan['azimut_deg'], 180)
        self.assertEqual(pan['roof_type'], 'flat')


class ZonesEtudeDuDevisTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ACAL58', slug='acal58')
        self.client_ = Client.objects.create(company=self.co, nom='Plat')

    def _devis(self, reference, layout, statut=Devis.Statut.BROUILLON):
        return Devis.objects.create(
            company=self.co, client=self.client_, reference=reference,
            statut=statut, roof_layout=layout)

    def test_zones_etude_du_devis_tilt_pose(self):
        layout = _layout(_zone_plate_inclinee())
        stocke, _etude = _calepinage_range(
            layout, extract_roof_config(layout), 7.44)
        devis = self._devis('DEV-ACAL58-001', stocke)
        devis.refresh_from_db()

        zones = zones_etude_du_devis(devis)

        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]['tilt'], 10.0)
        self.assertEqual(zones[0]['azimuth'], 0.0)   # PVGIS : 0 = Sud

    def test_dry_run_liste_le_devis_envoye_sans_le_reecrire(self):
        layout = _layout(_zone_plate_inclinee())
        ancien = dict(layout)
        # La géométrie STOCKÉE avant ACAL58 : la pente du toit (0°).
        ancien['_pans_geometry'] = [{'label': 'Toit plat', 'kwc': 7.44,
                                     'inclinaison_deg': 0,
                                     'azimut_deg': None}]
        devis = self._devis('DEV-ACAL58-ENV', ancien,
                            statut=Devis.Statut.ENVOYE)
        self._devis('DEV-ACAL58-BRO', dict(ancien))

        sortie = StringIO()
        call_command('acal_dryrun_orientation', stdout=sortie)
        texte = sortie.getvalue()

        self.assertIn('DEV-ACAL58-ENV', texte)
        self.assertNotIn('DEV-ACAL58-BRO', texte)
        self.assertIn('inclinaison 0 → 10', texte)
        self.assertIn('Devis concernés : 1', texte)
        devis.refresh_from_db()
        self.assertEqual(devis.roof_layout['_pans_geometry'][0]
                         ['inclinaison_deg'], 0)
