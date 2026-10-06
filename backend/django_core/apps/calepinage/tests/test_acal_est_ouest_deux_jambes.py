# -*- coding: utf-8 -*-
"""ACAL139 — un pan est-ouest est simulé en DEUX jambes (face E, face O),
réparties selon les modules posés de chaque face.

Constat C-ACAL-081. Avant : un seul appel PVGIS à l'aspect −90 pour tout le
pan (la face ouest simulée comme si elle regardait l'est) et un seul groupe
électrique. Désormais ``pvgis_serie.jambes_du_pan`` rend les deux faces et
leur part du kWc ; la simulation simule chaque jambe à SON aspect et
rejoint les deux en UN pan au rapport ; l'électrique forme deux groupes.

Chaîne RÉELLE (``simuler_calepinage``), météo REJOUÉE par un client qui
répond une série DISTINCTE par aspect (est le matin, ouest l'après-midi) —
aucun mock de la chaîne.

Run :
    python manage.py test apps.calepinage.tests.test_acal_est_ouest_deux_jambes
"""
from __future__ import annotations

import copy
import unittest

from django.test import SimpleTestCase

from apps.calepinage.services.chaines import (
    affectation, concevoir_par_pan, groupes_electriques,
)
from apps.calepinage.services.electrique import TemperaturesSite
from apps.calepinage.services.etapes.inter_rangees import _parts_est_ouest
from apps.calepinage.services.pvgis_serie import jambes_du_pan
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.tests.test_acal_multi_pans import (
    _ClientParOrientation, _materiel,
)
from apps.calepinage.tests.test_calx5_simulation import REGLAGES, _Calepinage

#: 12 modules face E puis 8 face W, intercalés comme l'atelier les pose.
FACES = ['E', 'W'] * 8 + ['E'] * 4


def _zone_est_ouest(faces=FACES, azimut=90.0):
    panneaux = [{'cx': 1.2 * rang, 'cy': 0.0, 'n': rang + 1}
                for rang in range(len(FACES))]
    if faces is not None:
        for panneau, face in zip(panneaux, faces):
            panneau['face'] = face
    # Comme l'exemple du contrat (zone « Pan Est-Ouest libre ») : le TOIT
    # porte son azimut et sa pente, les TABLES les leurs (geometry).
    return {'id': 'eo', 'label': 'PAN-EO', 'roofType': 'flat',
            'facingAzimuthDeg': azimut, 'pitchDeg': 10.0,
            'geometry': {'family': 'eastwest', 'azimuthDeg': azimut,
                         'tiltDeg': 10.0, 'count': len(panneaux),
                         'panels': panneaux}}


def _zone(label, modules, azimut):
    return {'id': label.lower(), 'label': label,
            'geometry': {'count': modules, 'azimuthDeg': azimut,
                         'tiltDeg': 10.0, 'family': 'surimposition'}}


def _layout(*zones):
    return {'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898},
            'zones': list(zones)}


def _simuler(layout):
    client = _ClientParOrientation()
    rendu = simuler_calepinage(
        _Calepinage(layout=copy.deepcopy(layout)), client=client,
        materiel=_materiel(30.0), reglages=REGLAGES, enregistrer=False)
    return rendu['blocs'], client


class DeuxJambesTest(SimpleTestCase):

    def test_deux_appels_pvgis_par_face(self):
        blocs, client = _simuler(_layout(_zone_est_ouest()))
        aspects = sorted({demande['aspect_deg'] for demande in client.demandes})
        self.assertEqual(aspects, [-90.0, 90.0])
        # UN pan au rapport (les jambes sont internes).
        self.assertEqual(len(blocs['production']['par_pan']), 1)
        # Le profil horaire porte les DEUX faces : la crête du matin (est,
        # 60 %) ET celle de l'après-midi (ouest, 40 %). Une seule jambe à
        # l'aspect −90 (avant) donnait 16 h ≈ 22 % de 10 h ; deux jambes
        # 60/40 en donnent ≈ 77 %.
        serie = blocs['serie_horaire']
        self.assertIn('p_w', serie['colonnes'])
        par_heure = {}
        for point in serie['points']:
            par_heure[point['heure']] = (par_heure.get(point['heure'], 0.0)
                                         + (point.get('p_w') or 0.0))
        self.assertGreater(par_heure[10], par_heure[16])
        self.assertGreater(par_heure[16] / par_heure[10], 0.6)

    def test_parts_selon_les_faces_posees(self):
        jambes = jambes_du_pan({'azimut_deg': 90.0, 'modules': 20,
                                'geometry': _zone_est_ouest()['geometry']})
        self.assertEqual([(j['face'], j['azimut_face_deg'], j['modules'])
                          for j in jambes],
                         [('E', 90.0, 12), ('W', 270.0, 8)])
        self.assertAlmostEqual(jambes[0]['part'], 0.6)
        self.assertAlmostEqual(jambes[1]['part'], 0.4)
        self.assertFalse(any(j['hypothese'] for j in jambes))
        # La MÊME lecture sert l'ombre des rangées.
        self.assertEqual(_parts_est_ouest(
            {'geometry': _zone_est_ouest()['geometry']}), (0.6, 0.4, False))

        # La production du pan = celle de deux pans séparés de 12 (est) et
        # 8 (ouest) modules : la somme des deux jambes.
        eo, _ = _simuler(_layout(_zone_est_ouest()))
        separes, _ = _simuler(_layout(_zone('EST', 12, 90.0),
                                      _zone('OUEST', 8, 270.0)))
        p50_eo = eo['production']['total']['p50_kwh']
        p50_separes = separes['production']['total']['p50_kwh']
        self.assertAlmostEqual(p50_eo, p50_separes, delta=p50_separes * 0.005)

    def test_repli_moitie_avec_avertissement(self):
        geometrie = _zone_est_ouest(faces=None)['geometry']
        jambes = jambes_du_pan({'azimut_deg': 90.0, 'modules': 20,
                                'geometry': geometrie})
        self.assertEqual([j['part'] for j in jambes], [0.5, 0.5])
        self.assertTrue(all(j['hypothese'] for j in jambes))
        blocs, client = _simuler(_layout(_zone_est_ouest(faces=None)))
        self.assertTrue(any('répartition est/ouest supposée' in texte
                            for texte in blocs.get('avertissements') or ()))
        self.assertEqual(sorted({d['aspect_deg'] for d in client.demandes}),
                         [-90.0, 90.0])

    def test_un_pan_sud_reste_une_seule_jambe(self):
        jambes = jambes_du_pan({'azimut_deg': 180.0, 'modules': 12,
                                'geometry': {'family': 'surimposition'}})
        self.assertEqual(len(jambes), 1)
        self.assertEqual(jambes[0]['part'], 1.0)


MODULE = {'vmp_v': 41.4, 'voc_v': 49.3, 'isc_a': 18.59, 'imp_a': 17.59,
          'pmax_wc': 710.0}
ONDULEUR = {'n_mppt': 2, 'mppt_v_min': 120.0, 'mppt_v_max': 500.0,
            'v_max_abs': 600.0, 'i_max_mppt_a': 40.0, 'ac_kw': 15.0,
            'phases': 3}


class DeuxGroupesElectriquesTest(unittest.TestCase):

    def test_deux_groupes_electriques(self):
        layout = _layout(_zone_est_ouest())
        groupes = groupes_electriques(layout)
        self.assertEqual([(g.label, g.nb_modules, g.azimut_deg)
                          for g in groupes],
                         [('PAN-EO', 12, 90.0), ('PAN-EO', 8, 270.0)])

        temperatures = TemperaturesSite(froid_c=-5.0, chaud_c=70.0,
                                        source='saisie', detail='saisie')
        conception = concevoir_par_pan(
            layout, module_specs=MODULE, onduleur_specs=ONDULEUR,
            temperatures=temperatures, phases=3)
        self.assertEqual(len(conception.repartitions), 2)
        lignes = affectation(conception)
        self.assertEqual(len(lignes), 20)
        # Aucune chaîne ne mélange un module de l'est et un de l'ouest.
        faces_par_chaine = {}
        for ligne in lignes:
            if ligne['chaine'] is None:
                continue
            rang = int(ligne['module'].rsplit('#', 1)[1])
            faces_par_chaine.setdefault(ligne['chaine'], set()).add(
                FACES[rang - 1])
        self.assertTrue(faces_par_chaine)
        for faces in faces_par_chaine.values():
            self.assertEqual(len(faces), 1, faces_par_chaine)
        self.assertEqual({next(iter(f)) for f in faces_par_chaine.values()},
                         {'E', 'W'})
