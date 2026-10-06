"""ACAL142 — la série horaire persistée APRÈS batterie / autoconsommation /
hors réseau, et l'écrêtage publié par onduleur depuis la phase ONDULEUR.

Constat C-ACAL-083 : ``resultat.serie_horaire`` était figée juste après la
chaîne de pertes, AVANT les blocs aval — l'export CSV horaire promettait
``charge_kwh`` / ``reseau_import_kwh`` / ``reseau_export_kwh`` « pour refaire
le calcul » et ne les livrait jamais ; ``production.par_onduleur`` ne
publiait aucune perte d'écrêtage alors que la phase ONDULEUR existe (ACAL53).

Chaîne RÉELLE (``simuler_calepinage``, client rejoué) et agrégation RÉELLE ;
aucun mock.

Run :
    python manage.py test apps.calepinage.tests.test_acal_serie_apres_batterie -v2
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from apps.calepinage.services.agregation_electrique import (
    MOTIF_SANS_CASCADE, agregation_production,
)
from apps.calepinage.services.chaine_pertes import ETAPES_ONDULEUR
from apps.calepinage.services.simulation import simuler_calepinage

from .test_acal_multi_pans import _ClientParOrientation
from .test_calx183_par_chaine import _affectation, _production
from .test_calx5_simulation import LAYOUT, MATERIEL, REGLAGES, _Calepinage

REGLAGES_FUSEAU = copy.deepcopy(REGLAGES)
REGLAGES_FUSEAU['imagerie'] = {'fuseau': 'Africa/Casablanca'}


def _simuler(layout, materiel=MATERIEL):
    return simuler_calepinage(
        _Calepinage(layout=layout), client=_ClientParOrientation(1000.0),
        materiel=materiel, reglages=REGLAGES_FUSEAU,
        enregistrer=False)['blocs']


class SerieApresBlocsAvalTest(SimpleTestCase):

    def test_colonnes_charge_et_reseau_persistees(self):
        layout = copy.deepcopy(LAYOUT)
        # Deux années × deux jours × 24 h : la relève couvre chaque heure.
        layout['consumption'] = {'import_intervalle': {
            'valeurs': [0.8] * 96, 'origine': 'Relevé SYNTHÉTIQUE de test'}}
        blocs = _simuler(layout)

        self.assertEqual(blocs['autoconsommation']['motif_absence'], '')
        points = blocs['serie_horaire']['points']
        self.assertTrue(points)
        for colonne in ('charge_kwh', 'reseau_import_kwh',
                        'reseau_export_kwh'):
            self.assertIn(colonne, blocs['serie_horaire']['colonnes'],
                          colonne)
            self.assertTrue(any(point.get(colonne) is not None
                                for point in points), colonne)
        # La borne de volume reste celle de la série (aucun point ajouté).
        self.assertLessEqual(len(points), 96)


class EcretageParOnduleurTest(SimpleTestCase):

    def test_ecretage_par_onduleur_publie(self):
        materiel = copy.deepcopy(MATERIEL)
        materiel['onduleur']['ac_kw'] = 5.0
        blocs = _simuler(copy.deepcopy(LAYOUT), materiel)
        phase = [etape for etape in blocs['cascade']['etapes']
                 if etape['etape'] in ETAPES_ONDULEUR]
        ecretage = next(e for e in phase if e['etape'] == 'ecretage')
        self.assertEqual(ecretage['motif_omission'], '')

        table = _affectation('PAN-A', 10)
        bloc = agregation_production(_production(10, table), table,
                                     cascade_onduleur=phase)

        ligne = bloc['par_onduleur'][0]
        self.assertEqual(ligne['perte_ecretage_pct'], ecretage['perte_pct'])
        self.assertEqual(ligne['motif_ecretage'], '')
        # Par CHAÎNE, aucune cascade n'existe : les pertes restent omises.
        for chaine in bloc['par_chaine']:
            self.assertIsNone(chaine['perte_ecretage_pct'])
            self.assertEqual(chaine['motif_ecretage'], MOTIF_SANS_CASCADE)

    def test_sans_phase_onduleur_la_perte_est_omise_motivee(self):
        table = _affectation('PAN-A', 10)
        bloc = agregation_production(_production(10, table), table)
        ligne = bloc['par_onduleur'][0]
        self.assertIsNone(ligne['perte_ecretage_pct'])
        self.assertEqual(ligne['motif_ecretage'], MOTIF_SANS_CASCADE)
