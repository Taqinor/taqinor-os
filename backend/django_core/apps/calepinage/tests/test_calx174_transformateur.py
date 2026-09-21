"""CALX174 — le transformateur ne se retranche que s'il existe.

Aucune base, aucun réseau : une nuit, un midi, et une déclaration d'entrée
électrique en dur.

Run :
    python manage.py test apps.calepinage.tests.test_calx174_transformateur
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import transformateur

#: Une heure de nuit (rien ne sort) et une heure à 50 kW.
SERIE = {'pas_minutes': 60, 'points': [
    {'annee': 2020, 'mois': 1, 'jour': 15, 'heure': 3, 'p_w': 0.0},
    {'annee': 2020, 'mois': 7, 'jour': 15, 'heure': 12, 'p_w': 50000.0},
]}

A_VIDE_KW = 0.5
EN_CHARGE_KW = 2.0
NOMINAL_KW = 100.0


def saisie(valeur, source='saisie'):
    return {'valeur': valeur, 'source': source,
            'reference': 'Procès-verbal d’essai du transformateur'}


COMPLET = {
    'perte_a_vide_kw': saisie(A_VIDE_KW),
    'perte_en_charge_kw_nominale': saisie(EN_CHARGE_KW),
    'puissance_nominale_kw': saisie(NOMINAL_KW),
}


def contexte_de(declaration):
    if declaration is None:
        return {'entree_electrique': {}}
    return {'entree_electrique': {'transformateur': declaration}}


class AucunTransformateurTest(unittest.TestCase):
    """Sans transformateur, l'étape se tait — et ne réclame RIEN."""

    def test_le_motif_est_neutre(self):
        _, etape = transformateur.appliquer(SERIE, contexte_de(None))
        self.assertEqual(etape['motif_omission'],
                         transformateur.MOTIF_ABSENT)

    def test_aucun_champ_n_est_reclame_a_l_utilisateur(self):
        _, etape = transformateur.appliquer(SERIE, contexte_de(None))
        self.assertNotIn('Champ manquant', etape['motif_omission'])
        self.assertNotIn('saisi', etape['motif_omission'])

    def test_un_contexte_vide_se_tait_de_la_meme_facon(self):
        rendue, etape = transformateur.appliquer(SERIE, {})
        self.assertEqual(etape['motif_omission'],
                         transformateur.MOTIF_ABSENT)
        self.assertIs(rendue, SERIE)

    def test_un_declare_false_explicite_vaut_pas_de_transformateur(self):
        _, etape = transformateur.appliquer(
            SERIE, contexte_de({'declare': False}))
        self.assertEqual(etape['motif_omission'],
                         transformateur.MOTIF_ABSENT)


class DeclareSansPertesTest(unittest.TestCase):
    """Déclaré mais muet : les DEUX champs sont nommés."""

    def setUp(self):
        _, self.etape = transformateur.appliquer(SERIE, contexte_de(True))

    def test_les_deux_champs_sont_nommes(self):
        self.assertIn('perte_a_vide_kw', self.etape['motif_omission'])
        self.assertIn('perte_en_charge_kw_nominale',
                      self.etape['motif_omission'])

    def test_le_champ_a_saisir_pointe_l_entree_electrique(self):
        self.assertIn('entree_electrique.transformateur',
                      self.etape['motif_omission'])

    def test_une_perte_sans_source_ne_vaut_pas_saisie(self):
        declaration = dict(COMPLET)
        declaration['perte_a_vide_kw'] = {'valeur': 0.5, 'source': ''}
        _, etape = transformateur.appliquer(
            SERIE, contexte_de(declaration))
        self.assertIn('perte_a_vide_kw', etape['motif_omission'])
        self.assertNotIn('perte_en_charge_kw_nominale',
                         etape['motif_omission'])

    def test_sans_puissance_nominale_la_loi_en_i2_est_refusee(self):
        declaration = dict(COMPLET)
        declaration.pop('puissance_nominale_kw')
        _, etape = transformateur.appliquer(
            SERIE, contexte_de(declaration))
        self.assertIn('puissance_nominale_kw', etape['motif_omission'])
        self.assertIn('I²', etape['motif_omission'])

    def test_la_serie_ressort_intacte(self):
        rendue, _ = transformateur.appliquer(SERIE, contexte_de(True))
        self.assertEqual(etapes.energie_kwh(rendue), 50.0)


class ApplicationTest(unittest.TestCase):
    """À vide partout, en charge en I² — et la nuit ne paie que le premier."""

    def setUp(self):
        self.rendue, self.etape = transformateur.appliquer(
            SERIE, contexte_de(COMPLET))

    def test_la_nuit_ne_porte_que_la_perte_a_vide(self):
        nuit = self.rendue['points'][0]
        self.assertAlmostEqual(nuit['p_w'], -A_VIDE_KW * 1000.0, places=6)

    def test_l_heure_en_charge_porte_les_deux_pertes(self):
        midi = self.rendue['points'][1]
        attendu = 50.0 - A_VIDE_KW - EN_CHARGE_KW * (50.0 / NOMINAL_KW) ** 2
        self.assertAlmostEqual(midi['p_w'], attendu * 1000.0, places=6)

    def test_la_perte_en_charge_suit_le_carre_du_taux_de_charge(self):
        quart = {'pas_minutes': 60,
                 'points': [{'p_w': 25000.0}, {'p_w': 50000.0}]}
        rendue, _ = transformateur.appliquer(quart, contexte_de(COMPLET))
        perte_quart = 25.0 - rendue['points'][0]['p_w'] / 1000.0 - A_VIDE_KW
        perte_moitie = 50.0 - rendue['points'][1]['p_w'] / 1000.0 - A_VIDE_KW
        self.assertAlmostEqual(perte_moitie / perte_quart, 4.0, places=6)

    def test_les_deux_energies_sont_publiees_separement(self):
        self.assertAlmostEqual(self.etape['entree']['energie_a_vide_kwh'],
                               2 * A_VIDE_KW, places=3)
        self.assertAlmostEqual(self.etape['entree']['energie_en_charge_kwh'],
                               EN_CHARGE_KW * 0.25, places=3)

    def test_chaque_saisie_voyage_avec_sa_source(self):
        for champ in ('perte_a_vide_kw', 'perte_en_charge_kw_nominale',
                      'puissance_nominale_kw'):
            self.assertEqual(self.etape['entree'][champ]['source'], 'saisie')

    def test_la_reference_cite_pvsyst(self):
        self.assertIn('PVsyst', self.etape['reference'])

    def test_la_serie_d_entree_n_est_jamais_modifiee_sur_place(self):
        self.assertEqual(SERIE['points'][1]['p_w'], 50000.0)


class DansLaChaineTest(unittest.TestCase):
    """L'étape passe par l'ordonnanceur sans rien lui devoir."""

    def test_l_etape_est_appliquee_et_mesuree(self):
        _, cascade = appliquer_chaine(SERIE, contexte_de(COMPLET))
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'transformateur')
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['kwh_avant'], 50.0)
        self.assertGreater(etape['perte_kwh'], 0.0)
        self.assertFalse(etape['gain'])

    def test_une_chaine_sans_transformateur_omet_l_etape(self):
        _, cascade = appliquer_chaine(SERIE, {})
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'transformateur')
        self.assertEqual(etape['motif_omission'],
                         transformateur.MOTIF_ABSENT)
        self.assertIsNone(etape['perte_pct'])


if __name__ == '__main__':
    unittest.main()
