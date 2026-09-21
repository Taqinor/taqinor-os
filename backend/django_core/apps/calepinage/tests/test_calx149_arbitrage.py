"""CALX149 — le poste CALCULÉ prime sur le poste saisi, et on le DIT.

Le catalogue accepte une saisie pour quinze postes ; plusieurs savent
désormais se calculer. Sans arbitrage, la perte thermique de la fiche et le
« thermique » saisi se retranchaient l'un après l'autre. Ce fichier garde les
quatre branches de la règle : calculé prime, saisie écartée et publiée,
saisie sourcée en relais, saisie sans source jamais appliquée.

Aucune base de données, aucun réseau : des modules d'étape postiches.

Run :
    python manage.py test apps.calepinage.tests.test_calx149_arbitrage
"""
from __future__ import annotations

import copy
import types
import unittest
from unittest import mock

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import (
    POSTE_PAR_ETAPE, appliquer_chaine)

#: 10 kWh d'essai, en quatre heures rondes.
SERIE = {
    'pas_minutes': 60,
    'points': [{'p_w': 1000.0}, {'p_w': 2000.0}, {'p_w': 3000.0},
               {'p_w': 4000.0}],
}


def calcul(pct, *, source, libelle, entree):
    """Un module d'étape qui CALCULE une perte de ``pct`` %."""
    def appliquer(serie, contexte):
        return etapes.mettre_a_l_echelle(serie, 1.0 - pct / 100.0), \
            etapes.etape_appliquee(libelle, source=source, entree=entree)
    return types.SimpleNamespace(appliquer=appliquer)


def sans_entree(motif):
    """Un module livré qui s'OMET faute d'entrée."""
    def appliquer(serie, contexte):
        return serie, etapes.etape_omise('Étape d’essai', motif)
    return types.SimpleNamespace(appliquer=appliquer)


def lancer(contexte, modules=None):
    modules = modules or {}
    with mock.patch.object(etapes, 'charger',
                           side_effect=lambda p: modules.get(p)):
        _, bloc = appliquer_chaine(SERIE, contexte)
    return bloc, {etape['etape']: etape for etape in bloc['etapes']}


class CalculePrimeTest(unittest.TestCase):
    """L'étape calculée s'applique, et la saisie est publiée écartée."""

    def test_le_thermique_calcule_ecarte_la_saisie_et_le_dit(self):
        contexte = {'postes_saisis': [
            {'poste': 'thermique', 'libelle': 'Échauffement', 'pct': 8.0,
             'source': 'saisie'}]}
        modules = {'thermique': calcul(
            20.0, source='fiche', libelle='Échauffement calculé',
            entree='temp_coeff_pmax_pct_c')}
        _, par_nom = lancer(contexte, modules)
        etape = par_nom['thermique']

        self.assertEqual(etape['source'], 'fiche')
        self.assertEqual(etape['perte_pct'], 20.0,
                         'c’est le CALCUL qui s’applique, pas les 8 % saisis.')
        ecartee = etape['entree']['saisie_ecartee']
        self.assertEqual(ecartee['poste'], 'thermique')
        self.assertEqual(ecartee['etape'], 'thermique')
        self.assertEqual(ecartee['pct'], 8.0)
        self.assertEqual(ecartee['source'], 'saisie')
        self.assertIn('ÉCARTÉ', ecartee['motif'])
        self.assertIn('LECTURE', ecartee['motif'].upper())
        self.assertEqual(etape['entree']['champ'], 'temp_coeff_pmax_pct_c',
                         'l’entrée réelle de l’étape reste lisible.')

    def test_l_ohmique_dc_calcule_ecarte_la_saisie(self):
        contexte = {'postes_saisis': [
            {'poste': 'ohmique_dc', 'pct': 1.5, 'source': 'societe'}]}
        modules = {'ohmique_dc': calcul(
            0.5, source='calcul', libelle='Chutes DC',
            entree='longueurs_dc_du_plan')}
        _, par_nom = lancer(contexte, modules)
        etape = par_nom['ohmique_dc']
        self.assertEqual(etape['perte_pct'], 0.5)
        self.assertEqual(etape['entree']['saisie_ecartee']['pct'], 1.5)

    def test_sans_saisie_l_entree_de_l_etape_reste_telle_quelle(self):
        modules = {'thermique': calcul(
            10.0, source='fiche', libelle='x', entree='temp_coeff')}
        _, par_nom = lancer({}, modules)
        self.assertEqual(par_nom['thermique']['entree'], 'temp_coeff')


class SaisieEnRelaisTest(unittest.TestCase):
    """Non calculable + saisie SOURCÉE : c'est la saisie qui s'applique."""

    def test_une_saisie_sourcee_s_applique_avec_sa_source_inchangee(self):
        contexte = {'postes_saisis': [
            {'poste': 'indisponibilite', 'libelle': 'Indisponibilité',
             'pct': 2.0, 'source': 'societe', 'reference': 'Contrat O&M'}]}
        _, par_nom = lancer(contexte)
        etape = par_nom['indisponibilite']
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['source'], 'societe')
        self.assertEqual(etape['reference'], 'Contrat O&M')
        self.assertEqual(etape['perte_pct'], 2.0)
        self.assertEqual(etape['entree'], 'poste_saisi:indisponibilite')

    def test_un_module_qui_s_omet_laisse_la_place_a_la_saisie_sourcee(self):
        contexte = {'postes_saisis': [
            {'poste': 'lid', 'pct': 1.0, 'source': 'texte'}]}
        modules = {'lid': sans_entree('Aucune technologie de cellule lue.')}
        _, par_nom = lancer(contexte, modules)
        self.assertEqual(par_nom['lid']['perte_pct'], 1.0)
        self.assertEqual(par_nom['lid']['source'], 'texte')

    def test_le_renommage_de_catalogue_est_respecte(self):
        contexte = {'postes_saisis': [
            {'poste': 'irradiance', 'pct': 1.0, 'source': 'societe'}]}
        _, par_nom = lancer(contexte)
        self.assertEqual(par_nom['niveau_irradiance']['perte_pct'], 1.0,
                         'le poste « irradiance » du catalogue est servi par '
                         'l’étape « niveau_irradiance ».')

    def test_une_exclusivite_l_emporte_sur_la_saisie(self):
        contexte = {
            'meteo': {'horizon': {'origine': 'dem_pvgis'}},
            'postes_saisis': [{'poste': 'iam', 'pct': 3.0,
                               'source': 'societe'}],
        }
        _, par_nom = lancer(contexte)
        self.assertIsNone(par_nom['horizon']['kwh_apres'],
                          'PVGIS a déjà retranché l’horizon : rien ne le '
                          'retranche une seconde fois.')
        self.assertEqual(par_nom['iam']['perte_pct'], 3.0)


class SaisieSansSourceTest(unittest.TestCase):
    """Une saisie sans source n'entre JAMAIS — et elle est nommée."""

    def setUp(self):
        self.contexte = {'postes_saisis': [
            {'poste': 'salissure', 'pct': 4.0, 'source': None}]}
        self.bloc, self.par_nom = lancer(self.contexte)

    def test_elle_n_entre_pas_dans_la_cascade(self):
        etape = self.par_nom['salissure']
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['kwh_apres'])
        self.assertIsNone(etape['perte_pct'])

    def test_son_nom_figure_dans_postes_non_sources(self):
        self.assertIn('salissure', self.bloc['postes_non_sources'])

    def test_le_motif_nomme_le_poste_et_le_manque(self):
        motif = self.par_nom['salissure']['motif_omission']
        self.assertIn('salissure', motif)
        self.assertIn('SANS SOURCE', motif)

    def test_un_pourcentage_illisible_ne_s_applique_pas_non_plus(self):
        bloc, par_nom = lancer({'postes_saisis': [
            {'poste': 'onduleur', 'pct': 'beaucoup', 'source': 'societe'}]})
        self.assertIsNone(par_nom['onduleur']['kwh_apres'])
        self.assertIn('onduleur', bloc['postes_non_sources'])


class PertesResteUneListePlateTest(unittest.TestCase):
    """D-CALX 11 : la chaîne LIT les postes saisis, elle ne les réécrit pas."""

    def test_la_liste_saisie_ressort_octet_pour_octet(self):
        postes = [{'poste': 'thermique', 'pct': 8.0, 'source': 'saisie'},
                  {'poste': 'mismatch', 'pct': 2.0, 'source': None}]
        contexte = {'postes_saisis': postes}
        temoin = copy.deepcopy(postes)
        modules = {'thermique': calcul(5.0, source='fiche', libelle='x',
                                       entree='y')}
        lancer(contexte, modules)
        self.assertEqual(postes, temoin,
                         'la cascade s’ajoute à côté de « pertes » : elle ne '
                         'la réécrit pas.')

    def test_les_deux_postes_du_catalogue_hors_chaine_ne_cassent_rien(self):
        contexte = {'postes_saisis': [
            {'poste': 'vieillissement', 'pct': 0.5, 'source': 'fiche'},
            {'poste': 'auxiliaires_nocturnes', 'pct': 0.2,
             'source': 'mesure'}]}
        bloc, _ = lancer(contexte)
        noms = {etape['etape'] for etape in bloc['etapes']}
        self.assertNotIn('vieillissement', noms)
        self.assertNotIn('auxiliaires_nocturnes', noms)
        self.assertNotIn('vieillissement', set(POSTE_PAR_ETAPE))


if __name__ == '__main__':
    unittest.main()
