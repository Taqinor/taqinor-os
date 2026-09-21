"""CALX165 — l'étape « qualité module » n'applique que ce qui est saisi.

Aucune base de données, aucun réseau : une série de quatre heures, un
contexte minimal, et la vraie chaîne (``appliquer_chaine``).

CE QUI EST LU, ET POURQUOI JAMAIS LE TOTAL DE LA CHAÎNE
---------------------------------------------------------
Les douze champs que l'ordonnanceur publie AUTOUR de cette étape
(``kwh_avant``/``kwh_apres``, ``perte_pct``, ``gain``, ``motif_omission``)
se lisent sur la cascade : eux seuls sont attribuables à CETTE étape. La
chaîne en porte vingt-quatre : dès qu'une lane voisine en livre une, elle
réduit LÉGITIMEMENT la série, et un total de sortie cesserait de prouver
quoi que ce soit d'ici. L'énergie RENDUE par l'étape se vérifie donc par un
appel DIRECT à ``etapes.qualite_module.appliquer``.

Run :
    python manage.py test apps.calepinage.tests.test_calx165_qualite_module
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import qualite_module

ETAPE = 'qualite_module'

#: Quatre heures à 1, 2, 3 et 4 kW : 10 kWh tout rond, en chiffres d'essai.
SERIE = {
    'pas_minutes': 60,
    'points': [
        {'heure': 9, 'p_w': 1000.0},
        {'heure': 10, 'p_w': 2000.0},
        {'heure': 11, 'p_w': 3000.0},
        {'heure': 12, 'p_w': 4000.0},
    ],
}


def contexte_avec(minimum=None, maximum=None, regle=None, source='societe',
                  produit='Module PV 550 Wc', reference=''):
    """Le contexte d'une étape : la fiche, le réglage société, le nom."""
    fiche = {}
    if minimum is not None:
        fiche['tolerance_pmax_min_pct'] = minimum
    if maximum is not None:
        fiche['tolerance_pmax_max_pct'] = maximum
    contexte = {'fiche_module': fiche,
                'designations': {'module': produit}}
    if regle is not None:
        saisie = {'valeur': regle, 'reference': reference}
        if source is not None:
            saisie['source'] = source
        contexte['reglages_simulation'] = {'regle_qualite_module': saisie}
    return contexte


def cascade(contexte, serie=None):
    """L'étape TELLE QUE LA CHAÎNE la publie, douze champs compris."""
    _, bloc = appliquer_chaine(serie or SERIE, contexte)
    return next(e for e in bloc['etapes'] if e['etape'] == ETAPE)


def seule(contexte, serie=None):
    """``(serie, etape)`` de CETTE étape et d'elle seule.

    Le seul endroit où l'énergie rendue lui est attribuable : la chaîne
    complète porte les autres étapes, qui la réduisent légitimement.
    """
    return qualite_module.appliquer(serie or SERIE, contexte)


class ToleranceAbsenteTest(unittest.TestCase):
    """Sans tolérance publiée, l'étape se TAIT — en nommant le champ."""

    def test_le_motif_nomme_le_champ_de_fiche(self):
        etape = cascade(contexte_avec(regle='quart_pvsyst'))
        self.assertIn('FicheTechnique.tolerance_pmax_min_pct',
                      etape['motif_omission'])

    def test_le_motif_nomme_le_produit(self):
        etape = cascade(contexte_avec(regle='quart_pvsyst'))
        self.assertIn('Module PV 550 Wc', etape['motif_omission'])

    def test_elle_se_tait_meme_sans_regle_saisie(self):
        etape = cascade(contexte_avec())
        self.assertIn('FicheTechnique.tolerance_pmax_min_pct',
                      etape['motif_omission'])

    def test_aucun_chiffre_n_est_publie(self):
        etape = cascade(contexte_avec())
        for champ in ('kwh_apres', 'perte_kwh', 'perte_pct', 'source',
                      'entree', 'reference'):
            self.assertIsNone(etape[champ], champ)

    def test_la_serie_ressort_inchangee(self):
        rendue, etape = seule(contexte_avec())
        self.assertNotEqual(etape['motif_omission'], '')
        self.assertEqual(etapes.energie_kwh(rendue), 10.0)


class RegleNonSaisieTest(unittest.TestCase):
    """AUCUN quart n'est appliqué tant que la société n'a rien choisi."""

    def test_le_motif_nomme_le_reglage_de_societe(self):
        etape = cascade(contexte_avec(minimum=0, maximum=3))
        self.assertIn('parametres.simulation.regle_qualite_module',
                      etape['motif_omission'])

    def test_aucune_energie_n_est_touchee(self):
        rendue, _ = seule(contexte_avec(minimum=0, maximum=3))
        self.assertEqual(etapes.energie_kwh(rendue), 10.0)
        etape = cascade(contexte_avec(minimum=0, maximum=3))
        self.assertIsNone(etape['perte_pct'])

    def test_une_regle_sans_source_ne_vaut_pas_saisie(self):
        etape = cascade(contexte_avec(minimum=0, maximum=3,
                                      regle='quart_pvsyst', source=None))
        self.assertIn('parametres.simulation.regle_qualite_module',
                      etape['motif_omission'])

    def test_une_regle_inconnue_est_nommee_et_jamais_devinee(self):
        etape = cascade(contexte_avec(minimum=0, maximum=3,
                                      regle='un_quart_a_la_louche'))
        self.assertIn('un_quart_a_la_louche', etape['motif_omission'])
        self.assertIn('quart_pvsyst', etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])


class TriPositifTest(unittest.TestCase):
    """Une plage 0/+3 % avec la règle du quart est un GAIN, pas une perte."""

    def setUp(self):
        self.etape = cascade(contexte_avec(minimum=0, maximum=3,
                                           regle='quart_pvsyst'))

    def test_l_etape_se_declare_en_gain(self):
        self.assertTrue(self.etape['gain'])

    def test_la_perte_publiee_est_negative(self):
        self.assertLess(self.etape['perte_pct'], 0.0)
        self.assertEqual(self.etape['perte_pct'], -0.75)

    def test_l_energie_augmente_d_un_quart_de_la_plage(self):
        rendue, _ = seule(contexte_avec(minimum=0, maximum=3,
                                        regle='quart_pvsyst'))
        self.assertAlmostEqual(etapes.energie_kwh(rendue), 10.075, places=6)

    def test_elle_nomme_sa_source_et_ses_deux_champs(self):
        self.assertEqual(self.etape['source'], 'fiche')
        self.assertIn('tolerance_pmax_min_pct', self.etape['entree'])
        self.assertIn('tolerance_pmax_max_pct', self.etape['entree'])

    def test_la_reference_cite_pvsyst_et_la_regle_de_la_societe(self):
        self.assertIn('PVsyst', self.etape['reference'])
        self.assertIn('quart_pvsyst', self.etape['reference'])
        self.assertIn('societe', self.etape['reference'])


class PlageSymetriqueTest(unittest.TestCase):
    """±3 % avec le quart : une PERTE, du quart de la largeur de plage."""

    def setUp(self):
        self.etape = cascade(contexte_avec(minimum=-3, maximum=3,
                                           regle='quart_pvsyst'))

    def test_c_est_une_perte_et_non_un_gain(self):
        self.assertFalse(self.etape['gain'])
        self.assertEqual(self.etape['perte_pct'], 1.5)

    def test_l_energie_diminue(self):
        rendue, _ = seule(contexte_avec(minimum=-3, maximum=3,
                                        regle='quart_pvsyst'))
        self.assertAlmostEqual(etapes.energie_kwh(rendue), 9.85, places=6)


class AutresReglesTest(unittest.TestCase):
    """La borne basse et la moyenne sont deux décisions distinctes."""

    def test_la_borne_basse_est_retenue_telle_quelle(self):
        etape = cascade(contexte_avec(minimum=-3, maximum=3,
                                      regle='borne_basse'))
        self.assertEqual(etape['perte_pct'], 3.0)

    def test_la_borne_basse_n_a_pas_besoin_de_la_borne_haute(self):
        etape = cascade(contexte_avec(minimum=-3, regle='borne_basse'))
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree'], 'tolerance_pmax_min_pct')

    def test_la_moyenne_d_une_plage_symetrique_ne_coute_rien(self):
        etape = cascade(contexte_avec(minimum=-3, maximum=3,
                                      regle='moyenne'))
        self.assertEqual(etape['perte_pct'], 0.0)
        self.assertFalse(etape['gain'])

    def test_la_moyenne_exige_les_deux_bornes(self):
        etape = cascade(contexte_avec(minimum=-3, regle='moyenne'))
        self.assertIn('FicheTechnique.tolerance_pmax_max_pct',
                      etape['motif_omission'])

    def test_le_quart_exige_les_deux_bornes(self):
        etape = cascade(contexte_avec(minimum=0, regle='quart_pvsyst'))
        self.assertIn('FicheTechnique.tolerance_pmax_max_pct',
                      etape['motif_omission'])

    def test_la_regle_est_lue_sans_tenir_compte_de_la_casse(self):
        etape = cascade(contexte_avec(minimum=0, maximum=3,
                                      regle='  Quart_PVsyst '))
        self.assertEqual(etape['motif_omission'], '')
        self.assertTrue(etape['gain'])


class RegleAucuneTest(unittest.TestCase):
    """« Aucune » est une décision déclarée, pas une donnée manquante."""

    def setUp(self):
        self.etape = cascade(contexte_avec(minimum=-3, maximum=3,
                                           regle='aucune'))

    def test_l_etape_figure_dans_la_cascade_avec_son_motif(self):
        self.assertIn('AUCUNE perte de qualité module',
                      self.etape['motif_omission'])
        self.assertIn('societe', self.etape['motif_omission'])

    def test_elle_ne_publie_aucun_chiffre(self):
        self.assertIsNone(self.etape['perte_pct'])
        self.assertIsNone(self.etape['kwh_apres'])

    def test_la_serie_ressort_inchangee(self):
        rendue, etape = seule(contexte_avec(minimum=-3, maximum=3,
                                            regle='aucune'))
        self.assertNotEqual(etape['motif_omission'], '')
        self.assertEqual(etapes.energie_kwh(rendue), 10.0)


class PlageIncoherenteTest(unittest.TestCase):
    """Une plage retournée n'est jamais remise à l'endroit en silence."""

    def test_une_borne_haute_sous_la_borne_basse_omet_l_etape(self):
        etape = cascade(contexte_avec(minimum=3, maximum=-3,
                                      regle='quart_pvsyst'))
        self.assertIn('INFÉRIEURE', etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])

    def test_aucune_colonne_d_energie_omet_l_etape(self):
        serie = {'pas_minutes': 60, 'points': [{'t2m_c': 21.0}]}
        _, bloc = appliquer_chaine(
            serie, contexte_avec(minimum=0, maximum=3,
                                 regle='quart_pvsyst'))
        etape = next(e for e in bloc['etapes'] if e['etape'] == ETAPE)
        self.assertIn('p_w', etape['motif_omission'])


class LectureDeLaFicheTest(unittest.TestCase):
    """La fiche se lit sous les noms que ``specs_for_produit`` publie."""

    def test_un_objet_porteur_est_lu_comme_un_dict_de_specs(self):
        class _Fiche:
            tolerance_pmax_min_pct = 0
            tolerance_pmax_max_pct = 3

        self.assertEqual(qualite_module._tolerance_min(_Fiche()), 0)
        self.assertEqual(qualite_module._tolerance_max(_Fiche()), 3)

    def test_les_champs_lus_sont_ceux_que_calx60_publie(self):
        self.assertEqual(qualite_module.CHAMP_MIN, 'tolerance_pmax_min_pct')
        self.assertEqual(qualite_module.CHAMP_MAX, 'tolerance_pmax_max_pct')

    def test_la_cle_de_reglage_figure_au_registre_de_calx145(self):
        from apps.calepinage.services.parametres_cles import (
            SECTION_SIMULATION, registre)
        self.assertIn(qualite_module.CLE_REGLAGE,
                      registre(SECTION_SIMULATION))

    def test_aucun_coefficient_n_est_ecrit_hors_des_regles_nommees(self):
        self.assertEqual(sorted(qualite_module.REGLES),
                         ['aucune', 'borne_basse', 'moyenne',
                          'quart_pvsyst'])


if __name__ == '__main__':
    unittest.main()
