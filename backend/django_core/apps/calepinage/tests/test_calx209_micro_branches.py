# -*- coding: utf-8 -*-
"""CALX209 — les branches AC d'un champ à micro-onduleurs.

Trois fiches, trois comportements, et le troisième est celui qui compte :

1. **fiche avec plafond d'unités** (``opt_ac_unites_max_par_branche``) — les
   branches sont coupées à ce plafond, motif citant la fiche ;
2. **fiche avec le seul courant** (``opt_ac_i_max_a``) — la branche est bornée
   par son COURANT CUMULÉ sous le plus grand calibre normalisé du barème
   (NF C 15-100 / IEC 60947-2), et le motif dit que c'est une borne
   NORMATIVE, pas une recommandation constructeur ;
3. **fiche muette sur les deux** — une seule branche, déclarée NON
   VÉRIFIABLE : aucun plafond n'est supposé.

Et dans tous les cas : l'écran MPPT n'est pas rendu pour ce régime.

``SimpleTestCase`` : aucune base, le matériel est injecté (``materiel=``).

Run :
    python manage.py test apps.calepinage.tests.test_calx209_micro_branches -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import (
    CLE_MICRO_ONDULEURS, evaluation_electrique, resultat_calepinage,
    temperatures_site,
)
from apps.calepinage.services.micro_onduleurs import (
    CHAMP_I_MAX, CHAMP_UNITES_MAX, MOTIF_ECRAN_MPPT, MOTIF_SANS_BORNE,
    ORIGINE_BORNE_CALIBRE, ORIGINE_BORNE_FICHE, REGIME_BRANCHE_AC,
    branches_du_champ, est_micro_onduleur,
)

MODULE = {
    'vmp_v': 34.0, 'voc_v': 41.0, 'isc_a': 13.8, 'imp_a': 13.0,
    'pmax_wc': 550.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 120.0, 'mppt_v_max': 850.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 1,
}

#: Une fiche d'OPTIMISEUR (sortie continue) — aucun champ ``ac_*``.
OPTIMISEUR_DC = {
    'pmax_in_w': 800.0, 'v_in_min': 12.0, 'v_in_max': 60.0,
    'i_in_max_a': 20.0, 'modules_par_optimiseur': 1,
    'v_out_nominal_v': 40.0,
}

#: Une fiche de MICRO-ONDULEUR : la sortie est ALTERNATIVE.
MICRO_PLAFOND = {
    'pmax_in_w': 800.0, 'v_in_max': 60.0, 'i_in_max_a': 20.0,
    'modules_par_optimiseur': 1,
    'ac_kw': 0.365, 'ac_tension_v': 230.0, 'ac_i_max_a': 1.6,
    'ac_unites_max_par_branche': 4,
}
MICRO_COURANT_SEUL = {cle: valeur for cle, valeur in MICRO_PLAFOND.items()
                      if cle != 'ac_unites_max_par_branche'}
MICRO_MUET = {cle: valeur for cle, valeur in MICRO_PLAFOND.items()
              if cle not in ('ac_unites_max_par_branche', 'ac_i_max_a')}

LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-SUD', 'geometry': {'count': 10, 'azimuthDeg': 180.0,
                                      'tiltDeg': 15.0}}]}


class _Calepinage:
    pk = 209
    statut = 'brouillon'

    def __init__(self):
        self.roof_layout = LAYOUT
        self.resultat = {'entree_electrique': {
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0}}
        self.company = None


def _materiel(optimiseur=None):
    return {
        'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': optimiseur,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai',
                         'optimiseur': 'Micro d essai' if optimiseur else ''},
        'absents': (),
    }


def _conception():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


class DiscriminantDeFicheTest(SimpleTestCase):
    """Une sortie ALTERNATIVE publiée = un micro-onduleur, jamais autrement."""

    def test_une_fiche_optimiseur_continue_n_est_pas_un_micro_onduleur(self):
        self.assertFalse(est_micro_onduleur(OPTIMISEUR_DC))

    def test_une_fiche_a_sortie_alternative_en_est_un(self):
        self.assertTrue(est_micro_onduleur(MICRO_MUET))

    def test_le_regime_ne_s_applique_pas_a_une_fiche_continue(self):
        rendu = branches_du_champ(_conception(), OPTIMISEUR_DC)

        self.assertFalse(rendu['applique'])
        self.assertEqual(rendu['branches'], [])
        self.assertEqual(rendu['regime'], REGIME_BRANCHE_AC)


class FicheAvecPlafondDUnitesTest(SimpleTestCase):
    """Le plafond du constructeur s'applique tel quel."""

    def test_dix_unites_a_quatre_par_branche_font_trois_branches(self):
        rendu = branches_du_champ(_conception(), MICRO_PLAFOND,
                                  designation='Micro d essai')

        self.assertTrue(rendu['applique'])
        self.assertEqual(rendu['unites'], 10)
        self.assertEqual(rendu['unites_max_par_branche'], 4)
        self.assertEqual([b['unites'] for b in rendu['branches']], [4, 4, 2])
        self.assertEqual([b['repere'] for b in rendu['branches']],
                         ['BR1', 'BR2', 'BR3'])

    def test_le_motif_de_coupure_cite_la_fiche(self):
        rendu = branches_du_champ(_conception(), MICRO_PLAFOND)

        self.assertEqual(rendu['borne']['origine'], ORIGINE_BORNE_FICHE)
        self.assertIn(CHAMP_UNITES_MAX,
                      rendu['branches'][0]['motif_de_coupure'])

    def test_le_courant_de_branche_est_le_cumul_des_unites(self):
        rendu = branches_du_champ(_conception(), MICRO_PLAFOND)

        # 4 unités × 1,6 A = 6,4 A ; 2 unités × 1,6 A = 3,2 A.
        self.assertAlmostEqual(rendu['branches'][0]['i_branche_a'], 6.4,
                               places=3)
        self.assertAlmostEqual(rendu['branches'][2]['i_branche_a'], 3.2,
                               places=3)

    def test_le_calibre_vient_du_bareme_normalise(self):
        from core.electrique.protections import calibre_disjoncteur

        rendu = branches_du_champ(_conception(), MICRO_PLAFOND)

        self.assertEqual(rendu['branches'][0]['calibre_a'],
                         calibre_disjoncteur(6.4))


class FicheAvecLeSeulCourantTest(SimpleTestCase):
    """Sans plafond d'unités, c'est le COURANT CUMULÉ qui borne — et il le dit."""

    def test_la_borne_vient_du_plus_grand_calibre_normalise(self):
        from core.electrique.protections import CALIBRES_DISJONCTEUR_A

        rendu = branches_du_champ(_conception(), MICRO_COURANT_SEUL)

        attendu = int(float(CALIBRES_DISJONCTEUR_A[-1]) // 1.6)
        self.assertEqual(rendu['borne']['origine'], ORIGINE_BORNE_CALIBRE)
        self.assertEqual(rendu['unites_max_par_branche'], attendu)

    def test_le_motif_dit_que_la_borne_est_normative_pas_constructeur(self):
        rendu = branches_du_champ(_conception(), MICRO_COURANT_SEUL)
        motif = rendu['branches'][0]['motif_de_coupure']

        self.assertIn(CHAMP_I_MAX, motif)
        self.assertIn('NF C 15-100', motif)
        self.assertIn('pas une recommandation', motif)

    def test_le_champ_tient_alors_sur_une_seule_branche(self):
        rendu = branches_du_champ(_conception(), MICRO_COURANT_SEUL)

        # 10 unités, borne à 156 : une seule branche, courant publié.
        self.assertEqual(len(rendu['branches']), 1)
        self.assertAlmostEqual(rendu['branches'][0]['i_branche_a'], 16.0,
                               places=3)


class FicheMuetteTest(SimpleTestCase):
    """Rien de publié ⇒ branche unique DÉCLARÉE non vérifiable."""

    def test_une_seule_branche_non_bornee(self):
        rendu = branches_du_champ(_conception(), MICRO_MUET)

        self.assertIsNone(rendu['borne'])
        self.assertIsNone(rendu['unites_max_par_branche'])
        self.assertEqual(len(rendu['branches']), 1)
        self.assertEqual(rendu['branches'][0]['unites'], 10)

    def test_le_motif_nomme_les_deux_champs_absents(self):
        rendu = branches_du_champ(_conception(), MICRO_MUET)

        self.assertEqual(rendu['motifs'], [MOTIF_SANS_BORNE])
        self.assertIn(CHAMP_UNITES_MAX, MOTIF_SANS_BORNE)
        self.assertIn(CHAMP_I_MAX, MOTIF_SANS_BORNE)

    def test_aucun_courant_ni_calibre_n_est_invente(self):
        rendu = branches_du_champ(_conception(), MICRO_MUET)

        self.assertIsNone(rendu['branches'][0]['i_branche_a'])
        self.assertIsNone(rendu['branches'][0]['calibre_a'])


class EcranMpptNonRenduTest(SimpleTestCase):
    """Dans ce régime, il n'y a pas d'entrée MPPT à montrer."""

    def test_le_bloc_declare_l_ecran_mppt_non_rendu(self):
        for fiche in (MICRO_PLAFOND, MICRO_COURANT_SEUL, MICRO_MUET):
            rendu = branches_du_champ(_conception(), fiche)
            self.assertFalse(rendu['ecran_mppt'])
            self.assertEqual(rendu['motif_mppt'], MOTIF_ECRAN_MPPT)

    def test_la_reference_opensolar_est_citee(self):
        rendu = branches_du_champ(_conception(), MICRO_PLAFOND)

        self.assertIn('support.opensolar.com', rendu['reference'])


class BranchementApplicatifTest(SimpleTestCase):
    """Le résultat publie le bloc, ses branches et leurs départs protégés."""

    def test_aucune_cle_sans_micro_onduleur_declare(self):
        resultat = resultat_calepinage(_Calepinage(), materiel=_materiel())

        self.assertNotIn(CLE_MICRO_ONDULEURS, resultat['electrique'])

    def test_une_fiche_optimiseur_continue_ne_publie_pas_le_bloc(self):
        resultat = resultat_calepinage(
            _Calepinage(), materiel=_materiel(OPTIMISEUR_DC))

        self.assertNotIn(CLE_MICRO_ONDULEURS, resultat['electrique'])

    def test_le_bloc_et_les_departs_qac_sont_publies(self):
        resultat = resultat_calepinage(
            _Calepinage(), materiel=_materiel(MICRO_PLAFOND))

        bloc = resultat['electrique'][CLE_MICRO_ONDULEURS]
        self.assertEqual(len(bloc['branches']), 3)
        reperes = [organe['repere'] for organe in resultat['protections']]
        self.assertIn('QAC.1', reperes)
        self.assertIn('QAC.3', reperes)
        # La liste reste HOMOGÈNE : mêmes clés pour tous les organes.
        clefs = {tuple(sorted(organe)) for organe in resultat['protections']}
        self.assertEqual(len(clefs), 1)

    def test_une_branche_sans_longueur_relevee_n_est_pas_dimensionnee(self):
        resultat = resultat_calepinage(
            _Calepinage(), materiel=_materiel(MICRO_PLAFOND))

        bloc = resultat['electrique'][CLE_MICRO_ONDULEURS]
        self.assertEqual(bloc['cables'], [])
        self.assertTrue(any('longueur_m' in message
                            for message in resultat['avertissements']))

    def test_la_borne_non_verifiable_est_une_alerte_pas_un_bloquant(self):
        evaluation = evaluation_electrique(
            _Calepinage(), materiel=_materiel(MICRO_MUET))

        self.assertIn(MOTIF_SANS_BORNE, evaluation['alertes'])
        self.assertNotIn(MOTIF_SANS_BORNE, evaluation['bloquants'])
