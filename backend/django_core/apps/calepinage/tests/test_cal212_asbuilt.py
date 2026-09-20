"""CAL212 — l'écart prévu/posé est MESURÉ, jamais estimé.

Le « Done » de la tâche, mot pour mot : « l'écart affiché est la différence
des deux saisies réelles, jamais estimé ; absence de saisie = écart non
affiché (test) ».

La comparaison est PURE (``comparer`` ne connaît que des dictionnaires), donc
ces tests tournent sans base. Les refus du modèle (pan obligatoire, date
saisie jamais future) sont vérifiés sur des instances NON enregistrées.
"""
from __future__ import annotations

import datetime
import unittest

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.calepinage.models import PoseReelle
from apps.calepinage.services.asbuilt import (
    MENTION_SANS_PREVU,
    MENTION_SANS_SAISIE,
    comparer,
)

PREVUS = [
    {'pan': 'Pan Sud', 'modules': 12},
    {'pan': 'Pan Nord', 'modules': 6},
]


def _ligne(lignes, pan):
    return next(ligne for ligne in lignes if ligne['pan'] == pan)


class EcartMesureTest(unittest.TestCase):

    def test_ecart_est_la_difference_des_deux_saisies(self):
        lignes = comparer(PREVUS, [
            {'pan': 'Pan Sud', 'modules_poses': 11,
             'ecarts_position': 'Une rangée décalée vers le faîtage',
             'releve_le': '2026-09-19'},
        ])
        sud = _ligne(lignes, 'Pan Sud')
        self.assertEqual(sud['prevu'], 12)
        self.assertEqual(sud['pose'], 11)
        self.assertEqual(sud['ecart'], -1)
        self.assertEqual(sud['mention'], '')
        self.assertIn('faîtage', sud['ecarts_position'])

    def test_ecart_nul_quand_le_pose_egale_le_prevu(self):
        lignes = comparer(PREVUS, [
            {'pan': 'Pan Sud', 'modules_poses': 12, 'releve_le': '2026-09-19'},
        ])
        self.assertEqual(_ligne(lignes, 'Pan Sud')['ecart'], 0)


class AbsenceDeSaisieTest(unittest.TestCase):

    def test_pan_non_releve_n_affiche_aucun_ecart(self):
        lignes = comparer(PREVUS, [])
        for pan in ('Pan Sud', 'Pan Nord'):
            ligne = _ligne(lignes, pan)
            self.assertIsNone(ligne['pose'], pan)
            self.assertIsNone(ligne['ecart'], pan)
            self.assertEqual(ligne['mention'], MENTION_SANS_SAISIE)

    def test_zero_n_est_jamais_servi_a_la_place_d_un_ecart_inconnu(self):
        lignes = comparer(PREVUS, [
            {'pan': 'Pan Sud', 'modules_poses': 12, 'releve_le': '2026-09-19'},
        ])
        self.assertEqual(_ligne(lignes, 'Pan Sud')['ecart'], 0)
        self.assertIsNone(_ligne(lignes, 'Pan Nord')['ecart'])

    def test_pan_pose_absent_du_prevu_reste_visible(self):
        lignes = comparer(PREVUS, [
            {'pan': 'Auvent', 'modules_poses': 4, 'releve_le': '2026-09-19'},
        ])
        auvent = _ligne(lignes, 'Auvent')
        self.assertIsNone(auvent['prevu'])
        self.assertEqual(auvent['pose'], 4)
        self.assertIsNone(auvent['ecart'])
        self.assertEqual(auvent['mention'], MENTION_SANS_PREVU)

    def test_aucun_pan_prevu_aucune_ligne_inventee(self):
        self.assertEqual(comparer([], []), [])


class PoseReelleModeleTest(SimpleTestCase):

    def test_pan_obligatoire(self):
        pose = PoseReelle(pan='  ', modules_poses=3,
                          releve_le=datetime.date(2026, 9, 19))
        with self.assertRaises(ValidationError) as capture:
            pose.clean()
        self.assertIn('pan', capture.exception.message_dict)

    def test_date_de_releve_obligatoire(self):
        pose = PoseReelle(pan='Pan Sud', modules_poses=3, releve_le=None)
        with self.assertRaises(ValidationError) as capture:
            pose.clean()
        self.assertIn('releve_le', capture.exception.message_dict)

    def test_date_future_refusee(self):
        demain = datetime.date.today() + datetime.timedelta(days=1)
        pose = PoseReelle(pan='Pan Sud', modules_poses=3, releve_le=demain)
        with self.assertRaises(ValidationError) as capture:
            pose.clean()
        self.assertIn('futur', capture.exception.message_dict['releve_le'][0])

    def test_un_seul_releve_par_pan(self):
        noms = {c.name for c in PoseReelle._meta.constraints}
        self.assertIn('uniq_pose_reelle_par_pan', noms)
