"""CAL129 — avec optimiseurs, la règle de chaîne CHANGE DE NATURE.

Le test est COMPARATIF, avec et sans fiche optimiseur (CAL116) déclarée, parce
que c'est la différence qui compte : sans optimiseur, la chaîne est fermée par
le Voc à froid du module ; avec, la tension est régulée et cette borne-là ne
s'applique plus — le champ refusé à tort redevient conforme.

Ce que le module NE FAIT PAS : inventer une longueur de chaîne admissible pour
le système à optimiseurs. La fiche CAL116 publie des bornes d'ENTRÉE, pas une
tension de sortie régulée : la borne de longueur est donc déclarée NON
VÉRIFIABLE et nommée, et la longueur retenue reste celle du repli prudent.

Run :
    python manage.py test apps.calepinage.tests.test_elec_optimiseurs -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    REGLE_CHAINE_MODULE, REGLE_CHAINE_OPTIMISEUR, evaluation_electrique,
    regle_de_chaine,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
OPTIMISEUR = {
    'pmax_in_w': 800.0, 'v_in_min': 12.0, 'v_in_max': 60.0,
    'i_in_max_a': 20.0, 'rendement_pct': 99.0, 'modules_par_optimiseur': 1,
}


class _Calepinage:
    pk = 3
    statut = 'brouillon'

    def __init__(self):
        self.roof_layout = {'version': 2, 'zones': [
            {'label': 'PAN-A', 'geometry': {'count': 12, 'azimuthDeg': 180.0,
                                            'tiltDeg': 15.0}}]}
        self.resultat = {'entree_electrique': {
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0}}
        self.company = None


def _materiel(optimiseur=None):
    return {
        'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': optimiseur,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai',
                         'optimiseur': 'Optimiseur d essai'
                         if optimiseur else ''},
        'absents': (),
    }


class RegleDeChaineTest(SimpleTestCase):
    """Sans optimiseur, RIEN ne change ; avec, la règle est substituée."""

    def test_sans_optimiseur_la_regle_reste_celle_du_module(self):
        regle = regle_de_chaine(MODULE, ONDULEUR, None)

        self.assertEqual(regle['regle'], REGLE_CHAINE_MODULE)
        self.assertIn('Voc À FROID du module', regle['libelle'])
        self.assertEqual(regle['verdicts_entree'], [])
        self.assertEqual(regle['bornes_non_verifiables'], [])

    def test_avec_optimiseur_la_borne_voc_module_ne_ferme_plus_la_chaine(self):
        regle = regle_de_chaine(MODULE, ONDULEUR, OPTIMISEUR,
                                designation='Optimiseur d essai')

        self.assertEqual(regle['regle'], REGLE_CHAINE_OPTIMISEUR)
        self.assertIn('RÉGULÉE', regle['libelle'])
        # La FICHE qui autorise la substitution est nommée.
        self.assertIn('Optimiseur d essai', regle['source'])

    def test_les_bornes_d_entree_de_l_optimiseur_sont_verifiees(self):
        regle = regle_de_chaine(MODULE, ONDULEUR, OPTIMISEUR,
                                designation='Optimiseur d essai')
        codes = {v['code']: v for v in regle['verdicts_entree']}

        self.assertEqual(sorted(codes), ['optimiseur_i_in_max_a',
                                         'optimiseur_pmax_in_w',
                                         'optimiseur_v_in_max'])
        # Voc module 49,6 V sous les 60 V d'entrée : conforme.
        self.assertTrue(codes['optimiseur_v_in_max']['conforme'])
        # Isc module 18,4 A sous les 20 A d'entrée : conforme.
        self.assertTrue(codes['optimiseur_i_in_max_a']['conforme'])

    def test_un_module_trop_puissant_pour_l_optimiseur_est_signale(self):
        regle = regle_de_chaine(MODULE, ONDULEUR,
                                dict(OPTIMISEUR, pmax_in_w=600.0))
        codes = {v['code']: v for v in regle['verdicts_entree']}

        self.assertFalse(codes['optimiseur_pmax_in_w']['conforme'])
        self.assertIn('AU-DESSUS DE', codes['optimiseur_pmax_in_w']['detail'])

    def test_borne_non_publiee_reste_non_verifiable(self):
        incomplete = {cle: valeur for cle, valeur in OPTIMISEUR.items()
                      if cle != 'i_in_max_a'}

        regle = regle_de_chaine(MODULE, ONDULEUR, incomplete)
        codes = {v['code']: v for v in regle['verdicts_entree']}

        self.assertIsNone(codes['optimiseur_i_in_max_a']['conforme'])
        self.assertIsNone(codes['optimiseur_i_in_max_a']['source'])

    def test_la_longueur_de_chaine_reste_non_verifiable_et_le_dit(self):
        regle = regle_de_chaine(MODULE, ONDULEUR, OPTIMISEUR)

        self.assertEqual(len(regle['bornes_non_verifiables']), 1)
        self.assertIn('repli PRUDENT', regle['bornes_non_verifiables'][0])


class ComparatifDansLeVerdictTest(SimpleTestCase):
    """Le verdict publié dit LAQUELLE des deux règles s'applique."""

    def test_sans_optimiseur_le_verdict_voc_est_evalue(self):
        evaluation = evaluation_electrique(_Calepinage(),
                                           materiel=_materiel())

        self.assertEqual(evaluation['regle_chaine']['regle'],
                         REGLE_CHAINE_MODULE)

    def test_avec_optimiseur_le_verdict_voc_est_substitue(self):
        from apps.calepinage.services.electrique import resultat_calepinage

        avec = resultat_calepinage(_Calepinage(),
                                   materiel=_materiel(OPTIMISEUR))
        sans = resultat_calepinage(_Calepinage(), materiel=_materiel())

        voc_avec = [v for v in avec['electrique']['verdicts']
                    if v['code'] == 'voc_cold_under_vmax'][0]
        voc_sans = [v for v in sans['electrique']['verdicts']
                    if v['code'] == 'voc_cold_under_vmax'][0]

        # Sans optimiseur : un verdict CHIFFRÉ et bloquant.
        self.assertIs(voc_sans['conforme'], True)
        self.assertTrue(voc_sans['bloquant'])
        # Avec optimiseur : la règle est substituée, la borne module ne
        # s'applique plus, et la note NOMME la fiche qui l'autorise.
        self.assertIsNone(voc_avec['conforme'])
        self.assertFalse(voc_avec['bloquant'])
        self.assertIn('SUBSTITUÉE', voc_avec['detail'])
        self.assertIn('Optimiseur d essai', voc_avec['detail'])
        self.assertEqual(avec['regle_chaine']['regle'],
                         REGLE_CHAINE_OPTIMISEUR)
        self.assertTrue(any('repli PRUDENT' in message
                            for message in avec['avertissements']))
