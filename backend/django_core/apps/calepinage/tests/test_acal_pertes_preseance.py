"""ACAL135 — pertes saisies : le poste du calepinage PRIME sur le réglage
société, la salissure mensuelle s'applique mois par mois, le forçage signé
existe, et chaque poste publie son statut.

Constat C-ACAL-070. Avant : un poste « salissure » mensuel saisi était
écarté dès que la société avait réglé une salissure (ou appliqué à plat, la
moyenne partout) ; un poste d'étape calculable ne pouvait pas être forcé ;
GET pertes/ ne disait pas ce que la chaîne avait fait de chaque poste.

Chaîne RÉELLE (``appliquer_chaine`` / ``simuler_calepinage``, client rejoué
CALX5), validation RÉELLE (``valider_postes``). Aucun mock de la source.

Run :
    python manage.py test apps.calepinage.tests.test_acal_pertes_preseance -v2
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import (
    SOURCE_SAISIE_FORCEE, STATUT_APPLIQUE, STATUT_ECARTE, STATUT_HORS_CHAINE,
    STATUT_NON_SIMULE, STATUT_NON_SOURCE, appliquer_chaine,
    statuts_des_postes,
)
from apps.calepinage.services.pertes import PertesInvalides, valider_postes
from apps.calepinage.services.simulation import simuler_calepinage

from .test_calx5_simulation import (
    MATERIEL, REGLAGES, _Calepinage, _ClientRejoue,
)

SERIE = {'pas_minutes': 60, 'points': [
    {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 12, 'p_w': 1000.0,
     'gi_w_m2': 400.0},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 12, 'p_w': 4000.0,
     'gi_w_m2': 1000.0},
]}

MENSUEL = [0.0] * 6 + [12.0, 12.0] + [0.0] * 4

#: L'onduleur publie son rendement : l'étape « onduleur » se CALCULE, et un
#: poste « onduleur » saisi est donc écarté — sauf forçage signé.
MATERIEL_RENDEMENT = copy.deepcopy(MATERIEL)
MATERIEL_RENDEMENT['onduleur']['rendement_euro_pct'] = 97.0


def _contexte_salissure(societe_pct=2.0):
    return {
        'reglages_simulation': {'salissure_mensuelle_pct': {
            'valeur': societe_pct, 'source': 'societe',
            'reference': 'réglage société'}},
        'postes_saisis': valider_postes([{
            'poste': 'salissure', 'mensuel': MENSUEL, 'source': 'saisie',
            'reference': 'Relevé de rinçage'}]),
    }


def _simuler(postes, materiel=MATERIEL_RENDEMENT):
    calepinage = _Calepinage(pertes=postes)
    return simuler_calepinage(calepinage, client=_ClientRejoue(),
                              materiel=materiel, reglages=REGLAGES,
                              enregistrer=False)['blocs']


def _etape(cascade, nom):
    return next(e for e in cascade['etapes'] if e['etape'] == nom)


class PreseanceTest(SimpleTestCase):

    def test_poste_calepinage_prime_sur_reglage_societe(self):
        _sortie, cascade = appliquer_chaine(SERIE, _contexte_salissure())
        etape = _etape(cascade, 'salissure')

        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['source'], 'saisie')
        self.assertEqual(etape['entree']['origine_du_reglage'], 'calepinage')
        self.assertEqual(etape['entree']['valeurs_pct'], MENSUEL)
        self.assertNotIn('saisie_ecartee', etape['entree'])

    def test_salissure_mensuelle_mois_par_mois(self):
        sortie, _cascade = appliquer_chaine(SERIE, _contexte_salissure())
        janvier, juillet = sortie['points']
        self.assertAlmostEqual(janvier['p_w'], 1000.0)
        self.assertAlmostEqual(juillet['p_w'], 4000.0 * 0.88)
        self.assertAlmostEqual(juillet['gi_w_m2'], 1000.0 * 0.88)

    def test_poste_mensuel_jamais_a_plat_sans_reglage(self):
        # Sans réglage société non plus : la saisie mensuelle reste mensuelle.
        contexte = _contexte_salissure()
        contexte['reglages_simulation'] = {}
        sortie, _cascade = appliquer_chaine(SERIE, contexte)
        janvier, juillet = sortie['points']
        self.assertAlmostEqual(janvier['p_w'], 1000.0)
        self.assertAlmostEqual(juillet['p_w'], 4000.0 * 0.88)


class ForcageTest(SimpleTestCase):

    def test_forcage_signe_applique(self):
        ecarte = _simuler(valider_postes([
            {'poste': 'onduleur', 'pct': 6.0, 'source': 'saisie'}]))
        force = _simuler(valider_postes([
            {'poste': 'onduleur', 'pct': 6.0, 'source': 'saisie',
             'force': True, 'motif_force': 'Mesuré sur site le 01/10.'}]))

        etape_ecartee = _etape(ecarte['cascade'], 'onduleur')
        self.assertIn('saisie_ecartee', etape_ecartee['entree'])
        etape_forcee = _etape(force['cascade'], 'onduleur')
        self.assertEqual(etape_forcee['source'], SOURCE_SAISIE_FORCEE)
        self.assertAlmostEqual(etape_forcee['perte_pct'], 6.0, delta=0.01)
        self.assertEqual(etape_forcee['entree']['motif_force'],
                         'Mesuré sur site le 01/10.')

    def test_forcage_sans_motif_refuse(self):
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'thermique', 'pct': 6.0,
                             'source': 'saisie', 'force': True}])
        self.assertEqual(refus.exception.champ, 'thermique.motif_force')

    def test_reference_saisie_conservee(self):
        postes = valider_postes([{'poste': 'salissure', 'pct': 2.0,
                                  'source': 'mesure',
                                  'reference': 'Relevé du 12/03/2026'}])
        self.assertEqual(postes[0]['reference'], 'Relevé du 12/03/2026')
        # Relire et réenregistrer sans toucher : octet-identique.
        self.assertEqual(valider_postes(copy.deepcopy(postes)), postes)
        forces = valider_postes([{'poste': 'thermique', 'pct': 6.0,
                                  'source': 'saisie', 'force': True,
                                  'motif_force': 'mesure'}])
        self.assertEqual(valider_postes(copy.deepcopy(forces)), forces)


class StatutTest(SimpleTestCase):

    def test_statut_publie_par_poste(self):
        postes = valider_postes([
            {'poste': 'onduleur', 'pct': 3.0, 'source': 'saisie'},
            {'poste': 'salissure', 'pct': 2.0, 'source': 'mesure'},
            {'poste': 'vieillissement', 'pct': 1.0, 'source': 'fiche'},
            {'poste': 'indisponibilite', 'pct': 1.0},
        ])
        blocs = _simuler(postes)
        statuts = statuts_des_postes(postes, blocs['cascade'])

        self.assertEqual(statuts['onduleur']['statut'], STATUT_ECARTE)
        self.assertEqual(statuts['onduleur']['etape'], 'onduleur')
        self.assertEqual(statuts['salissure']['statut'], STATUT_APPLIQUE)
        self.assertEqual(statuts['vieillissement']['statut'],
                         STATUT_HORS_CHAINE)
        self.assertTrue(statuts['vieillissement']['raison'])
        self.assertEqual(statuts['indisponibilite']['statut'],
                         STATUT_NON_SOURCE)
        self.assertTrue(any('vieillissement' in texte and 'HORS CHAÎNE'
                            in texte for texte in blocs['avertissements']))
        # Sans cascade fraîche : non simulé (sauf hors chaîne / sans source).
        sans = statuts_des_postes(postes, None)
        self.assertEqual(sans['onduleur']['statut'], STATUT_NON_SIMULE)
        self.assertEqual(sans['vieillissement']['statut'],
                         STATUT_HORS_CHAINE)

    def test_get_pertes_publie_les_postes_et_leur_statut(self):
        from apps.calepinage.views.simulation import publication_des_pertes

        class Pivot:
            pk = 1
            pertes = [{'poste': 'salissure', 'pct': 2.0, 'source': 'mesure'}]

        publie = publication_des_pertes(Pivot())
        ligne = publie['postes'][0]
        self.assertEqual(ligne['poste'], 'salissure')
        self.assertEqual(ligne['statut'], STATUT_NON_SIMULE)
        self.assertIs(ligne['force'], False)
        self.assertEqual(ligne['motif_force'], '')
        self.assertIn('raison', ligne)
