"""CALX147 — l'ordonnanceur de la chaîne de pertes tient ses trois refus.

Aucune base de données, aucun réseau : une série de quatre points, un
contexte vide, et des modules d'étape POSTICHES injectés par le registre.
C'est exactement ce que la chaîne verra en production — un nom d'étape, un
module qui existe ou non, et un couple ``(serie, etape)`` à vérifier.

Run :
    python manage.py test apps.calepinage.tests.test_calx147_chaine
"""
from __future__ import annotations

import json
import pathlib
import types
import unittest
from unittest import mock

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import (
    CLES_ETAPE_PUBLIEE, LIBELLES, ORDRE_ETAPES, ChaineInvalide,
    appliquer_chaine)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads(
    (ECHANTILLONS / 'calepinage_pertes_cascade.json').read_text(
        encoding='utf-8'))

#: Quatre heures à 1, 2, 3 et 4 kW : 10 kWh, en chiffres d'essai assumés.
SERIE = {
    'pas_minutes': 60,
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 9, 'p_w': 1000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 10, 'p_w': 2000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11, 'p_w': 3000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12, 'p_w': 4000.0},
    ],
}


def module_posticheur(fonction):
    """Un module d'étape minimal : un objet qui porte ``appliquer``."""
    return types.SimpleNamespace(appliquer=fonction)


def registre_de(modules):
    """Remplace la résolution par nom du registre par une table fixe."""
    return mock.patch.object(etapes, 'charger',
                             side_effect=lambda poste: modules.get(poste))


def identite(serie, contexte):
    return serie, etapes.etape_appliquee(
        'Étape neutre d’essai', source='fiche', entree='essai')


class SerieTest(unittest.TestCase):
    """La lecture de l'énergie ne devine rien au-delà d'une colonne connue."""

    def test_energie_lue_sur_la_colonne_presente(self):
        self.assertEqual(etapes.energie_kwh(SERIE), 10.0)

    def test_colonne_declaree_prime(self):
        serie = dict(SERIE, colonne_energie='p_ac_kw',
                     points=[{'p_w': 9999.0, 'p_ac_kw': 2.5}])
        self.assertEqual(etapes.energie_kwh(serie), 2.5)

    def test_aucune_colonne_lisible_rend_none_jamais_zero(self):
        self.assertIsNone(etapes.energie_kwh({'points': [{'t2m_c': 21.0}]}))

    def test_la_mise_a_l_echelle_ne_touche_pas_la_serie_recue(self):
        reduite = etapes.mettre_a_l_echelle(SERIE, 0.5)
        self.assertEqual(etapes.energie_kwh(reduite), 5.0)
        self.assertEqual(etapes.energie_kwh(SERIE), 10.0,
                         'la série d’entrée a été modifiée sur place.')


class ChaineVideTest(unittest.TestCase):
    """Contexte vide, aucun module livré : N étapes OMISES et rien d'autre."""

    def setUp(self):
        with registre_de({}):
            self.serie, self.cascade = appliquer_chaine(SERIE, {})

    def test_une_ligne_par_etape_declaree(self):
        self.assertEqual(len(self.cascade['etapes']), len(ORDRE_ETAPES))
        self.assertEqual(self.cascade['ordre'], list(ORDRE_ETAPES))

    def test_toutes_omises_avec_leur_motif_et_aucun_zero(self):
        for etape in self.cascade['etapes']:
            self.assertTrue(etape['motif_omission'].strip(),
                            f'{etape["etape"]} : omise sans motif.')
            self.assertIn(
                etape['etape'], etape['motif_omission'],
                f'{etape["etape"]} : le motif ne nomme pas le module '
                'attendu — l’écran ne saurait pas quoi livrer.')
            for champ in ('kwh_apres', 'perte_kwh', 'perte_pct'):
                self.assertIsNone(
                    etape[champ],
                    f'{etape["etape"]} : {champ} vaut {etape[champ]!r} alors '
                    'que l’étape est omise — un 0 se lirait « gratuite ».')
            self.assertIsNone(etape['source'])
            self.assertTrue(etape['libelle'].strip())

    def test_l_energie_est_inchangee_de_bout_en_bout(self):
        for etape in self.cascade['etapes']:
            self.assertEqual(etape['kwh_avant'], 10.0, etape['etape'])
        self.assertEqual(etapes.energie_kwh(self.serie), 10.0)

    def test_total_pct_reste_null_tant_qu_aucune_etape_ne_s_applique(self):
        self.assertIsNone(
            self.cascade['total_pct'],
            'Aucune étape appliquée n’est « 0 % de perte » : c’est « aucune '
            'étape n’a eu d’entrée ».')

    def test_les_rangs_suivent_l_ordre_declare(self):
        rangs = [etape['rang'] for etape in self.cascade['etapes']]
        self.assertEqual(rangs, list(range(1, len(ORDRE_ETAPES) + 1)))


class EtapeAppliqueeTest(unittest.TestCase):
    """Un module livré est appelé, et son passage est mesuré."""

    def test_une_etape_neutre_ne_retire_rien_mais_se_dit_appliquee(self):
        with registre_de({'iam': module_posticheur(identite)}):
            _, cascade = appliquer_chaine(SERIE, {})
        etape = next(e for e in cascade['etapes'] if e['etape'] == 'iam')
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['kwh_avant'], 10.0)
        self.assertEqual(etape['kwh_apres'], 10.0)
        self.assertEqual(etape['perte_kwh'], 0.0)
        self.assertEqual(etape['perte_pct'], 0.0)
        self.assertEqual(etape['source'], 'fiche')
        self.assertEqual(cascade['total_pct'], 0.0)

    def test_une_perte_reelle_est_positive_et_la_chaine_continue(self):
        def moitie(serie, contexte):
            return etapes.mettre_a_l_echelle(serie, 0.5), \
                etapes.etape_appliquee('Perte d’essai', source='societe',
                                       entree='essai')

        with registre_de({'iam': module_posticheur(moitie)}):
            serie, cascade = appliquer_chaine(SERIE, {})
        iam = next(e for e in cascade['etapes'] if e['etape'] == 'iam')
        self.assertEqual(iam['perte_kwh'], 5.0)
        self.assertEqual(iam['perte_pct'], 50.0)
        suivantes = [e for e in cascade['etapes'] if e['rang'] > iam['rang']]
        self.assertEqual(suivantes[0]['kwh_avant'], 5.0,
                         'la chaîne repart du dernier kwh_apres connu.')
        self.assertEqual(etapes.energie_kwh(serie), 5.0)
        self.assertEqual(cascade['total_pct'], 50.0)

    def test_un_gain_declare_porte_des_valeurs_negatives(self):
        def bonus(serie, contexte):
            return etapes.mettre_a_l_echelle(serie, 1.1), \
                etapes.etape_appliquee('Gain d’essai', source='fiche',
                                       entree='essai', gain=True)

        with registre_de({'bifacial': module_posticheur(bonus)}):
            _, cascade = appliquer_chaine(SERIE, {})
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'bifacial')
        self.assertTrue(etape['gain'])
        self.assertLess(etape['perte_kwh'], 0.0)
        self.assertLess(etape['perte_pct'], 0.0)


class RefusTest(unittest.TestCase):
    """Les trois refus — chacun NOMME l'étape fautive."""

    def _chaine(self, poste, fonction):
        with registre_de({poste: module_posticheur(fonction)}):
            return appliquer_chaine(SERIE, {})

    def test_un_gain_non_declare_est_refuse_en_nommant_l_etape(self):
        def gain_muet(serie, contexte):
            return etapes.mettre_a_l_echelle(serie, 1.1), \
                etapes.etape_appliquee('Gain muet', source='fiche',
                                       entree='essai')

        with self.assertRaises(ChaineInvalide) as capture:
            self._chaine('iam', gain_muet)
        self.assertEqual(capture.exception.etape, 'iam')
        self.assertIn('iam', str(capture.exception))

    def test_une_etape_omise_qui_modifie_la_serie_est_refusee(self):
        def omise_bavarde(serie, contexte):
            return etapes.mettre_a_l_echelle(serie, 0.9), \
                etapes.etape_omise('Omise d’essai', 'Aucune entrée saisie.')

        with self.assertRaises(ChaineInvalide) as capture:
            self._chaine('salissure', omise_bavarde)
        self.assertEqual(capture.exception.etape, 'salissure')

    def test_une_etape_appliquee_sans_source_est_refusee(self):
        def sans_source(serie, contexte):
            return serie, dict(etapes.etape_appliquee(
                'Sans source', source='fiche', entree='essai'), source='')

        with self.assertRaises(ChaineInvalide) as capture:
            self._chaine('lid', sans_source)
        self.assertEqual(capture.exception.etape, 'lid')

    def test_une_etape_qui_publie_un_rang_est_refusee(self):
        def trop_bavarde(serie, contexte):
            etape = etapes.etape_appliquee('Trop bavarde', source='fiche',
                                           entree='essai')
            etape['rang'] = 1
            return serie, etape

        with self.assertRaises(ChaineInvalide) as capture:
            self._chaine('thermique', trop_bavarde)
        self.assertIn('rang', str(capture.exception))

    def test_une_etape_qui_ne_rend_pas_un_couple_est_refusee(self):
        with self.assertRaises(ChaineInvalide) as capture:
            self._chaine('onduleur', lambda serie, contexte: serie)
        self.assertEqual(capture.exception.etape, 'onduleur')


class RegistreTest(unittest.TestCase):
    """Le mécanisme d'enregistrement : un nom, un module, rien d'autre."""

    def test_un_module_absent_rend_none_et_non_une_erreur(self):
        self.assertIsNone(etapes.charger('poste_qui_n_existe_pas'))

    def test_le_chemin_du_module_est_compose_a_un_seul_endroit(self):
        self.assertEqual(etapes.chemin_module('iam'),
                         'apps.calepinage.services.etapes.iam')

    def test_chaque_etape_declaree_porte_un_libelle_francais(self):
        for nom in ORDRE_ETAPES:
            self.assertIn(nom, LIBELLES)
            self.assertTrue(LIBELLES[nom].strip())

    def test_une_cle_de_reglage_hors_registre_est_refusee_en_la_nommant(self):
        with self.assertRaises(KeyError) as capture:
            etapes.reglage({}, 'coefficient_maison')
        self.assertIn('coefficient_maison', str(capture.exception))

    def test_un_reglage_sans_source_ne_vaut_pas_saisi(self):
        contexte = {'reglages_simulation': {'b0_iam': {'valeur': 0.05}}}
        self.assertIsNone(etapes.reglage(contexte, 'b0_iam'))
        contexte['reglages_simulation']['b0_iam']['source'] = 'societe'
        self.assertIsNotNone(etapes.reglage(contexte, 'b0_iam'))


class ConformiteAuContratTest(unittest.TestCase):
    """La cascade produite a la FORME du contrat committé (CALX141)."""

    def setUp(self):
        with registre_de({'iam': module_posticheur(identite)}):
            _, self.cascade = appliquer_chaine(
                SERIE, {'hash_entree': 'ab' * 32,
                        'postes_non_sources': ['availability']})
        self.modele = CONTRAT['exemple']['cascade']

    def test_les_cinq_cles_du_bloc(self):
        self.assertEqual(sorted(self.cascade), sorted(self.modele))

    def test_les_douze_champs_de_chaque_etape(self):
        attendus = set(self.modele['etapes'][0])
        self.assertEqual(attendus, set(CLES_ETAPE_PUBLIEE))
        for etape in self.cascade['etapes']:
            self.assertEqual(set(etape), attendus, etape['etape'])

    def test_la_cascade_produite_est_continue(self):
        etapes_publiees = self.cascade['etapes']
        dernier = etapes_publiees[0]['kwh_avant']
        for etape in etapes_publiees[1:]:
            self.assertEqual(etape['kwh_avant'], dernier, etape['etape'])
            if etape['kwh_apres'] is not None:
                dernier = etape['kwh_apres']

    def test_l_empreinte_et_les_postes_non_sources_sont_repris(self):
        self.assertEqual(self.cascade['hash_entree'], 'ab' * 32)
        self.assertEqual(self.cascade['postes_non_sources'], ['availability'])


if __name__ == '__main__':
    unittest.main()
