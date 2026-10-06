"""ACAL128 — le ratio de performance sur l'irradiation INCIDENTE.

Constat C-ACAL-080 : les étapes optiques (IAM, horizon, ombrage proche,
accès module, salissure) réécrivent ``gi_w_m2`` ; ``_sommes`` divisait
l'énergie par l'irradiation de la série FINALE — le PR valait 1,0 avec une
IAM de 3 %.

Désormais l'irradiation incidente est capturée UNE fois dans
``appliquer_chaine`` AVANT la première étape
(``cascade.irradiation_incidente_kwh_m2``), et
``production.total.performance_ratio``, ``par_pan[].performance_ratio`` et
``performance.irradiation_plan_kwh_m2`` la lisent.

Chaîne RÉELLE (``appliquer_chaine`` / ``simuler_calepinage``, client rejoué
CALX5) ; aucun mock de la chaîne.

Run :
    python manage.py test apps.calepinage.tests.test_acal_pr_incident -v2
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import (
    appliquer_chaine, irradiation_kwh_m2,
)
from apps.calepinage.services.pertes import valider_postes
from apps.calepinage.services.simulation import simuler_calepinage

from .test_acal_multi_pans import _ClientParOrientation, _layout, _zone
from .test_calx5_simulation import (
    MATERIEL, REGLAGES, _Calepinage, _ClientRejoue,
)

#: Le socle physique saisi (PR publié, D-ACAL-7) — tout à 0 % sauf la
#: salissure, dont l'étape RÉÉCRIT ``gi_w_m2``.
SOCLE = valider_postes([
    {'poste': nom, 'pct': pct, 'source': 'saisie', 'reference': 'essai'}
    for nom, pct in (('salissure', 3.0), ('mismatch', 0.0), ('lid', 0.0),
                     ('ohmique_dc', 0.0), ('ohmique_ac', 0.0),
                     ('qualite_module', 0.0), ('indisponibilite', 0.0))])

REGLAGES_FUSEAU = copy.deepcopy(REGLAGES)
REGLAGES_FUSEAU['imagerie'] = {'fuseau': 'Africa/Casablanca'}

SERIE = {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': [
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': heure,
     'p_w': 10.0 * globale, 'gi_w_m2': globale}
    for heure, globale in ((10, 600.0), (12, 900.0), (14, 700.0))]}


def _simuler(layout=None, client=None, reglages=REGLAGES_FUSEAU):
    calepinage = _Calepinage(layout=layout, pertes=copy.deepcopy(SOCLE))
    return simuler_calepinage(calepinage, client=client or _ClientRejoue(),
                              materiel=MATERIEL, reglages=reglages,
                              enregistrer=False)['blocs']


class PrIncidentTest(SimpleTestCase):

    def test_pr_inferieur_a_un_avec_iam(self):
        blocs = _simuler()
        total = blocs['production']['total']
        cascade = blocs['cascade']
        optiques = [etape['etape'] for etape in cascade['etapes']
                    if etape['etape'] in ('iam', 'salissure')
                    and not etape['motif_omission']
                    and (etape['perte_pct'] or 0) > 0]
        self.assertTrue(optiques, 'aucune étape optique active')

        self.assertIsNotNone(total['performance_ratio'])
        self.assertLess(total['performance_ratio'], 1.0)
        # PR = P50 / (kWc × irradiation incidente), à l'année moyenne.
        annees = total['annees_fenetre']
        attendu = total['p50_kwh'] / (
            total['kwc'] * cascade['irradiation_incidente_kwh_m2'] / annees)
        self.assertAlmostEqual(total['performance_ratio'], attendu,
                               delta=0.002)
        self.assertEqual(blocs['performance']['pr'],
                         total['performance_ratio'])

    def test_irradiation_incidente_capturee_avant_la_chaine(self):
        contexte = {'reglages_simulation': {'salissure_mensuelle_pct': {
            'valeur': 10.0, 'source': 'societe', 'reference': 'essai'}}}
        sortie, cascade = appliquer_chaine(SERIE, contexte)

        self.assertEqual(cascade['irradiation_incidente_kwh_m2'],
                         irradiation_kwh_m2(SERIE))
        self.assertAlmostEqual(cascade['irradiation_incidente_kwh_m2'], 2.2)
        # La série FINALE, elle, a vu son irradiance réduite de 10 %.
        self.assertAlmostEqual(irradiation_kwh_m2(sortie), 1.98)

    def test_par_pan_meme_definition(self):
        blocs = _simuler(layout=_layout(_zone(1, 10, 90.0),
                                        _zone(2, 6, 270.0)),
                         client=_ClientParOrientation())
        for ligne, ombrage in zip(blocs['production']['par_pan'],
                                  blocs['ombrage']['par_pan']):
            self.assertIsNotNone(ligne['performance_ratio'], ligne['pan'])
            self.assertLess(ligne['performance_ratio'], 1.0)
        self.assertIsNotNone(blocs['cascade']['irradiation_incidente_kwh_m2'])
        self.assertEqual(
            blocs['performance']['irradiation_plan_kwh_m2'],
            blocs['cascade']['irradiation_incidente_kwh_m2'])
