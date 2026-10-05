"""CIQ112 — mode de pose « bac acier » lu par la règle de pose, vocabulaire
unique avec le catalogue.

* un pan ``modePose=bac_acier`` à 3° ⇒ politique AFFLEURANTE ;
* le même pan SANS ``modePose`` ⇒ anti-ombrage (règle d'aujourd'hui) ;
* parité ``core.product_roles.TYPES_POSE`` ↔ ``SystemeFixation.ModePose``
  (``autre`` excepté) ;
* toit déclaré sur le lead → ``modePoseDeclare`` du document ;
* migration de choix réversible.
"""
import math
from importlib import import_module
from types import SimpleNamespace

from django.db import migrations
from django.test import SimpleTestCase

from apps.calepinage.models import SystemeFixation
from apps.calepinage.services.traduction import (
    _politique, entree_depuis_layout, mode_pose_declare_du_lead,
)
from core.product_roles import TYPES_POSE


def _rectangle(lon0, lat0, largeur_m, hauteur_m):
    dlon = largeur_m / (111320.0 * math.cos(math.radians(lat0))) / 2.0
    dlat = hauteur_m / 110540.0 / 2.0
    return [[lon0 - dlon, lat0 - dlat], [lon0 + dlon, lat0 - dlat],
            [lon0 + dlon, lat0 + dlat], [lon0 - dlon, lat0 + dlat]]


def _document(**pan):
    zone = {'id': 'z1', 'label': 'Bâtiment', 'pitchDeg': 3.0,
            'vertices': _rectangle(-7.6, 33.5, 30.0, 20.0)}
    zone.update(pan)
    return {
        'version': 2, 'pin': {'lat': 33.5, 'lng': -7.6}, 'panelWatt': 720,
        'panelLengthM': 2.278, 'panelWidthM': 1.134, 'activeAreaId': 'z1',
        'zones': [zone],
    }


class PolitiqueModePoseTests(SimpleTestCase):
    def test_bac_acier_peu_pentu_affleurant(self):
        politiques = dict(entree_depuis_layout(
            _document(modePose='bac_acier')).politiques)
        self.assertEqual(politiques['z1'].code, 'AFFLEURANT')

    def test_meme_pan_sans_mode_pose_inchange(self):
        politiques = dict(entree_depuis_layout(_document()).politiques)
        self.assertEqual(politiques['z1'].code, 'ANTI_OMBRAGE')

    def test_toit_plat_leste_anti_ombrage_meme_en_pente(self):
        self.assertEqual(
            _politique(False, 15.0, 33.5, 'toit_plat_leste').code,
            'ANTI_OMBRAGE')
        self.assertEqual(
            _politique(True, 0.0, 33.5, 'toiture_inclinee').code,
            'AFFLEURANT')

    def test_sol_et_ombriere_gardent_la_geometrie(self):
        for mode in ('sol', 'ombriere', None, ''):
            self.assertEqual(_politique(True, 2.0, 33.5, mode).code,
                             'ANTI_OMBRAGE', mode)

    def test_mode_pose_declare_du_document_servi_aux_pans(self):
        document = _document()
        document['modePoseDeclare'] = 'bac_acier'
        politiques = dict(entree_depuis_layout(document).politiques)
        self.assertEqual(politiques['z1'].code, 'AFFLEURANT')


class VocabulaireTests(SimpleTestCase):
    def test_parite_types_pose_mode_pose(self):
        valeurs = {v for v, _ in SystemeFixation.ModePose.choices} - {'autre'}
        self.assertEqual(valeurs, set(TYPES_POSE))

    def test_toit_declare_du_lead(self):
        self.assertEqual(mode_pose_declare_du_lead(
            SimpleNamespace(type_toiture='bac_acier')), 'bac_acier')
        self.assertEqual(mode_pose_declare_du_lead(
            SimpleNamespace(type_toiture='tuiles')), 'toiture_inclinee')
        # ambigu ⇒ muet (la géométrie reste juge)
        for toit in ('terrasse_beton', 'tole_metal', 'fibrociment', None):
            self.assertEqual(mode_pose_declare_du_lead(
                SimpleNamespace(type_toiture=toit)), '', toit)
        self.assertEqual(mode_pose_declare_du_lead(SimpleNamespace(
            type_surface='ombriere', type_toiture='bac_acier')), 'ombriere')

    def test_migration_choix_reversible(self):
        module = import_module(
            'apps.calepinage.migrations.0020_ciq112_mode_pose_bac_acier')
        ops = module.Migration.operations
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], migrations.AlterField)
        self.assertTrue(ops[0].reversible)
        self.assertIn(('bac_acier', 'Bac acier'), ops[0].field.choices)
