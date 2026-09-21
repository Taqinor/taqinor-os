"""CALX178 — le vieillissement se publie ANNÉE PAR ANNÉE, hors de la chaîne.

Aucune base, aucun réseau : un P50 d'année 1, une fiche produit et des
réglages société en dur.

Run :
    python manage.py test apps.calepinage.tests.test_calx178_vieillissement
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import (
    ORDRE_ETAPES, POSTES_HORS_CHAINE)
from apps.calepinage.services.etapes import vieillissement

P50_ANNEE1 = 13020.0

FICHE = {
    'degradation_annuelle_pct': 0.55,
    'degradation_annee1_pct': 2.0,
    'designation': 'JA Solar JAM72D40 580 MB',
}


def contexte_de(*, fiche=None, horizon=None, modele=None, fiches=None):
    reglages = {}
    if horizon is not None:
        reglages['annees_exploitation'] = {
            'valeur': horizon, 'source': 'societe',
            'reference': 'Décision société'}
    if modele is not None:
        reglages['modele_degradation'] = {
            'valeur': modele, 'source': 'societe',
            'reference': 'PV*SOL — Module degradation'}
    contexte = {'reglages_simulation': reglages}
    if fiche is not None:
        contexte['fiche_module'] = fiche
    if fiches is not None:
        contexte['fiches_modules'] = fiches
    return contexte


class HorsDeLaChaineTest(unittest.TestCase):
    """Le vieillissement n'est pas une étape horaire, et ne peut pas l'être."""

    def test_il_n_est_pas_dans_l_ordre_des_etapes(self):
        self.assertNotIn('vieillissement', ORDRE_ETAPES)

    def test_il_est_declare_hors_chaine_avec_sa_raison(self):
        self.assertIn('vieillissement', POSTES_HORS_CHAINE)
        self.assertIn('deux fois', POSTES_HORS_CHAINE['vieillissement'])

    def test_le_module_n_expose_aucun_appliquer(self):
        self.assertFalse(hasattr(vieillissement, 'appliquer'),
                         'un « appliquer » ferait de lui une étape horaire, '
                         'et le vieillissement se soustrairait deux fois.')

    def test_le_registre_ne_le_chargerait_de_toute_facon_jamais(self):
        module = etapes.charger('vieillissement')
        self.assertIsNone(getattr(module, 'appliquer', None))


class TableauPluriannuelTest(unittest.TestCase):
    """Le tableau, modèle linéaire, sur un horizon saisi."""

    def setUp(self):
        self.bloc = vieillissement.tableau_pluriannuel(
            P50_ANNEE1,
            contexte_de(fiche=FICHE, horizon=25, modele='lineaire'))

    def test_le_tableau_couvre_l_horizon_saisi(self):
        self.assertEqual(self.bloc['motif_omission'], '')
        self.assertEqual(len(self.bloc['annees']), 25)
        self.assertEqual(self.bloc['horizon_annees'], 25)
        self.assertEqual(self.bloc['source_horizon'], 'reglage')

    def test_le_facteur_de_l_annee_1_vaut_un_moins_la_degradation_annee1(self):
        self.assertAlmostEqual(self.bloc['annees'][0]['facteur'],
                               1 - 2.0 / 100.0, places=9)

    def test_le_facteur_decroit_de_facon_monotone(self):
        facteurs = [ligne['facteur'] for ligne in self.bloc['annees']]
        for precedent, suivant in zip(facteurs, facteurs[1:]):
            self.assertLess(suivant, precedent)

    def test_l_annee_1_egale_le_p50_de_la_chaine_a_l_unite_pres(self):
        self.assertAlmostEqual(self.bloc['annees'][0]['p50_kwh'],
                               P50_ANNEE1, delta=1.0)

    def test_la_production_suit_le_rapport_des_facteurs(self):
        premiere = self.bloc['annees'][0]
        dixieme = self.bloc['annees'][9]
        self.assertAlmostEqual(
            dixieme['p50_kwh'],
            P50_ANNEE1 * dixieme['facteur'] / premiere['facteur'], delta=0.01)

    def test_chaque_ligne_dit_sa_source(self):
        self.assertEqual(self.bloc['annees'][0]['source'], 'chaine')
        self.assertIn('lineaire', self.bloc['annees'][1]['source'])

    def test_la_reference_cite_les_trois_textes(self):
        self.assertIn('PV*SOL', self.bloc['reference'])
        self.assertIn('PVsyst', self.bloc['reference'])
        self.assertIn('OpenSolar', self.bloc['reference'])


class ModeleExponentielTest(unittest.TestCase):
    """Les deux modèles ne donnent pas la même courbe — et c'est le sujet."""

    def _facteurs(self, modele):
        bloc = vieillissement.tableau_pluriannuel(
            P50_ANNEE1, contexte_de(fiche=FICHE, horizon=25, modele=modele))
        return [ligne['facteur'] for ligne in bloc['annees']]

    def test_le_depart_est_le_meme_mais_la_fin_differe(self):
        lineaire = self._facteurs('lineaire')
        exponentiel = self._facteurs('exponentiel')
        self.assertAlmostEqual(lineaire[0], exponentiel[0], places=9)
        self.assertNotAlmostEqual(lineaire[-1], exponentiel[-1], places=4)

    def test_l_exponentiel_reste_au_dessus_du_lineaire(self):
        lineaire = self._facteurs('lineaire')
        exponentiel = self._facteurs('exponentiel')
        self.assertGreater(exponentiel[-1], lineaire[-1])

    def test_le_facteur_ne_descend_jamais_sous_zero(self):
        fiche = dict(FICHE, degradation_annuelle_pct=8.0)
        bloc = vieillissement.tableau_pluriannuel(
            P50_ANNEE1,
            contexte_de(fiche=fiche, horizon=25, modele='lineaire'))
        derniere = bloc['annees'][-1]
        self.assertEqual(derniere['facteur'], 0.0)
        self.assertEqual(derniere['p50_kwh'], 0.0)
        self.assertTrue(derniere['plancher'])


class OmissionTest(unittest.TestCase):
    """Chaque silence publie l'année 1 SEULE, et nomme ce qui manque."""

    def _bloc(self, **kwargs):
        return vieillissement.tableau_pluriannuel(
            P50_ANNEE1, contexte_de(**kwargs))

    def test_une_fiche_sans_degradation_publie_une_seule_annee(self):
        bloc = self._bloc(fiche={}, horizon=25, modele='lineaire')
        self.assertEqual(len(bloc['annees']), 1)
        self.assertEqual(bloc['annees'][0]['annee'], 1)
        self.assertIsNone(bloc['annees'][0]['facteur'])
        self.assertIn('degradation_annuelle_pct', bloc['motif_omission'])

    def test_la_degradation_de_premiere_annee_manquante_est_nommee(self):
        fiche = {'degradation_annuelle_pct': 0.55}
        bloc = self._bloc(fiche=fiche, horizon=25, modele='lineaire')
        self.assertIn('degradation_annee1_pct', bloc['motif_omission'])
        self.assertEqual(len(bloc['annees']), 1)

    def test_aucun_modele_choisi_omet_le_tableau_en_nommant_la_cle(self):
        bloc = self._bloc(fiche=FICHE, horizon=25)
        self.assertIn('modele_degradation', bloc['motif_omission'])
        self.assertEqual(len(bloc['annees']), 1)

    def test_un_modele_inconnu_est_refuse_en_le_citant(self):
        bloc = self._bloc(fiche=FICHE, horizon=25, modele='quadratique')
        self.assertIn('quadratique', bloc['motif_omission'])

    def test_ni_horizon_ni_garantie_n_invente_ni_20_ni_25(self):
        bloc = self._bloc(fiche=FICHE, modele='lineaire')
        self.assertEqual(len(bloc['annees']), 1)
        self.assertIsNone(bloc['horizon_annees'])
        self.assertIn('annees_exploitation', bloc['motif_omission'])
        self.assertIn('garantie_production_mois', bloc['motif_omission'])
        self.assertIn('Ni 20 ni 25 ans', bloc['motif_omission'])

    def test_un_p50_inconnu_ne_publie_aucune_annee(self):
        bloc = vieillissement.tableau_pluriannuel(
            None, contexte_de(fiche=FICHE, horizon=25, modele='lineaire'))
        self.assertEqual(bloc['annees'], [])
        self.assertIn('P50', bloc['motif_omission'])


class HorizonDeriveTest(unittest.TestCase):
    """À défaut de saisie, la plus LONGUE garantie de production le fixe."""

    def test_la_garantie_du_module_derive_l_horizon_et_nomme_le_produit(self):
        fiche = dict(FICHE, garantie_production_mois=360)
        bloc = vieillissement.tableau_pluriannuel(
            P50_ANNEE1, contexte_de(fiche=fiche, modele='lineaire'))
        self.assertEqual(bloc['horizon_annees'], 30)
        self.assertEqual(bloc['source_horizon'], 'derivee_fiche')
        self.assertEqual(bloc['produit_horizon'],
                         'JA Solar JAM72D40 580 MB')
        self.assertEqual(len(bloc['annees']), 30)

    def test_la_plus_longue_garantie_du_systeme_gagne(self):
        fiches = [
            dict(FICHE, garantie_production_mois=300, designation='Module A'),
            dict(FICHE, garantie_production_mois=360, designation='Module B'),
        ]
        bloc = vieillissement.tableau_pluriannuel(
            P50_ANNEE1,
            contexte_de(fiche=FICHE, modele='lineaire', fiches=fiches))
        self.assertEqual(bloc['horizon_annees'], 30)
        self.assertEqual(bloc['produit_horizon'], 'Module B')

    def test_la_saisie_societe_prime_sur_la_garantie(self):
        fiche = dict(FICHE, garantie_production_mois=360)
        bloc = vieillissement.tableau_pluriannuel(
            P50_ANNEE1,
            contexte_de(fiche=fiche, horizon=20, modele='lineaire'))
        self.assertEqual(bloc['horizon_annees'], 20)
        self.assertEqual(bloc['source_horizon'], 'reglage')


if __name__ == '__main__':
    unittest.main()
