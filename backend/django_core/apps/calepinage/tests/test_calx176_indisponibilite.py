"""CALX176 — l'indisponibilité se date, et publie DEUX pourcentages.

Aucune base, aucun réseau : une année horaire fabriquée ici, plus lumineuse
l'été que l'hiver, et des fenêtres d'arrêt en dur.

Run :
    python manage.py test apps.calepinage.tests.test_calx176_indisponibilite
"""
from __future__ import annotations

import calendar
import unittest

from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import indisponibilite

ANNEE = 2021
#: L'été produit 2,5 fois l'hiver : c'est ce qui rend une semaine de juin
#: plus coûteuse qu'une semaine de décembre.
PUISSANCE_ETE_W = 1000.0
PUISSANCE_HIVER_W = 400.0
HEURES_DE_JOUR = range(8, 18)


def annee_horaire():
    points = []
    for mois in range(1, 13):
        jours = calendar.monthrange(ANNEE, mois)[1]
        puissance = (PUISSANCE_ETE_W if 4 <= mois <= 9
                     else PUISSANCE_HIVER_W)
        for jour in range(1, jours + 1):
            for heure in range(24):
                points.append({
                    'annee': ANNEE, 'mois': mois, 'jour': jour,
                    'heure': heure,
                    'p_w': puissance if heure in HEURES_DE_JOUR else 0.0,
                })
    return {'pas_minutes': 60, 'points': points}


SERIE = annee_horaire()


def contexte_de(fenetres, *, source='societe'):
    return {'reglages_simulation': {
        'indisponibilite_fenetres': {
            'valeur': fenetres, 'source': source,
            'reference': "Journal d'exploitation"}}}


def semaine(debut, fin, motif='maintenance onduleur'):
    return [{'debut': debut, 'fin': fin, 'motif': motif}]


class OmissionTest(unittest.TestCase):
    """Rien de daté, rien de retranché — surtout pas 1 %."""

    def test_aucune_fenetre_omet_l_etape_en_nommant_la_cle(self):
        rendue, etape = indisponibilite.appliquer(SERIE, {})
        self.assertIn('indisponibilite_fenetres', etape['motif_omission'])
        self.assertIs(rendue, SERIE)
        self.assertIsNone(etape['source'])

    def test_une_liste_vide_vaut_aucune_fenetre(self):
        _, etape = indisponibilite.appliquer(SERIE, contexte_de([]))
        self.assertIn('indisponibilite_fenetres', etape['motif_omission'])

    def test_le_motif_refuse_explicitement_le_pourcentage_suppose(self):
        _, etape = indisponibilite.appliquer(SERIE, {})
        self.assertIn('jamais par un pourcentage annuel supposé',
                      etape['motif_omission'])

    def test_une_fenetre_hors_plage_est_refusee_en_citant_ses_dates(self):
        fenetres = semaine('2019-06-01', '2019-06-08')
        rendue, etape = indisponibilite.appliquer(
            SERIE, contexte_de(fenetres))
        self.assertIn('2019-06-01', etape['motif_omission'])
        self.assertIn('2019-06-08', etape['motif_omission'])
        self.assertIn('hors de la plage simulée', etape['motif_omission'])
        self.assertIs(rendue, SERIE)

    def test_une_fin_avant_le_debut_est_refusee_en_citant_ses_dates(self):
        fenetres = semaine('2021-06-08', '2021-06-01')
        _, etape = indisponibilite.appliquer(SERIE, contexte_de(fenetres))
        self.assertIn('2021-06-08', etape['motif_omission'])
        self.assertIn('ne suit pas son début', etape['motif_omission'])

    def test_une_date_illisible_est_refusee_en_la_citant(self):
        fenetres = semaine('juin dernier', '2021-06-08')
        _, etape = indisponibilite.appliquer(SERIE, contexte_de(fenetres))
        self.assertIn('juin dernier', etape['motif_omission'])

    def test_une_serie_sans_date_omet_l_etape_en_nommant_la_colonne(self):
        serie = {'pas_minutes': 60, 'points': [{'p_w': 1000.0}]}
        _, etape = indisponibilite.appliquer(
            serie, contexte_de(semaine('2021-06-01', '2021-06-08')))
        self.assertIn('serie_horaire.annee', etape['motif_omission'])


class SaisonnaliteTest(unittest.TestCase):
    """Une semaine de juin ne coûte pas une semaine de décembre."""

    def _etape(self, debut, fin):
        rendue, etape = indisponibilite.appliquer(
            SERIE, contexte_de(semaine(debut, fin)))
        self.assertEqual(etape['motif_omission'], '')
        return rendue, etape

    def test_une_semaine_de_juin_retire_plus_qu_une_semaine_de_decembre(self):
        _, juin = self._etape('2021-06-01', '2021-06-08')
        _, decembre = self._etape('2021-12-01', '2021-12-08')
        self.assertGreater(juin['entree']['energie_perdue_kwh'],
                           decembre['entree']['energie_perdue_kwh'])
        self.assertGreater(juin['entree']['pct_energie'],
                           decembre['entree']['pct_energie'])

    def test_les_deux_semaines_arretent_le_meme_temps(self):
        _, juin = self._etape('2021-06-01', '2021-06-08')
        _, decembre = self._etape('2021-12-01', '2021-12-08')
        self.assertEqual(juin['entree']['heures_arretees'], 168)
        self.assertEqual(decembre['entree']['heures_arretees'], 168)
        self.assertEqual(juin['entree']['pct_temps'],
                         decembre['entree']['pct_temps'])

    def test_le_pourcentage_de_temps_et_celui_d_energie_different(self):
        _, juin = self._etape('2021-06-01', '2021-06-08')
        self.assertNotAlmostEqual(juin['entree']['pct_temps'],
                                  juin['entree']['pct_energie'], places=3)

    def test_l_avertissement_francais_accompagne_les_deux_chiffres(self):
        _, juin = self._etape('2021-06-01', '2021-06-08')
        self.assertIn('ne se remplacent pas',
                      juin['entree']['avertissement'])
        self.assertIn('TEMPS', juin['entree']['avertissement'])
        self.assertIn('ÉNERGIE', juin['entree']['avertissement'])


class ArretTest(unittest.TestCase):
    """Les heures couvertes sortent à zéro, les autres sont intactes."""

    def setUp(self):
        self.rendue, self.etape = indisponibilite.appliquer(
            SERIE, contexte_de(semaine('2021-06-01', '2021-06-08')))

    def test_les_heures_de_la_fenetre_sont_a_zero(self):
        couvertes = [point for point in self.rendue['points']
                     if point['mois'] == 6 and point['jour'] <= 7]
        self.assertEqual(len(couvertes), 168)
        self.assertTrue(all(point['p_w'] == 0.0 for point in couvertes))

    def test_le_jour_de_la_borne_de_fin_reste_produit(self):
        huit_juin = [point for point in self.rendue['points']
                     if point['mois'] == 6 and point['jour'] == 8]
        self.assertTrue(any(point['p_w'] > 0.0 for point in huit_juin),
                        'la borne de fin est EXCLUE : le 8 juin produit.')

    def test_l_energie_retiree_est_celle_des_heures_de_jour(self):
        attendu = 7 * len(HEURES_DE_JOUR) * PUISSANCE_ETE_W / 1000.0
        self.assertAlmostEqual(self.etape['entree']['energie_perdue_kwh'],
                               attendu, places=3)

    def test_la_fenetre_est_republiee_avec_son_motif(self):
        publiee = self.etape['entree']['fenetres'][0]
        self.assertEqual(publiee['motif'], 'maintenance onduleur')
        self.assertTrue(publiee['debut'].startswith('2021-06-01'))

    def test_la_serie_d_entree_n_est_jamais_modifiee_sur_place(self):
        juin = [point for point in SERIE['points']
                if point['mois'] == 6 and point['jour'] == 1
                and point['heure'] == 12]
        self.assertEqual(juin[0]['p_w'], PUISSANCE_ETE_W)

    def test_deux_fenetres_se_cumulent_sans_se_compter_deux_fois(self):
        fenetres = (semaine('2021-06-01', '2021-06-08')
                    + semaine('2021-06-05', '2021-06-10', 'réseau coupé'))
        _, etape = indisponibilite.appliquer(SERIE, contexte_de(fenetres))
        self.assertEqual(etape['entree']['heures_arretees'], 9 * 24)


class DansLaChaineTest(unittest.TestCase):
    """L'étape passe par l'ordonnanceur sans rien lui devoir."""

    def test_l_etape_est_appliquee_et_mesuree(self):
        _, cascade = appliquer_chaine(
            SERIE, contexte_de(semaine('2021-06-01', '2021-06-08')))
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'indisponibilite')
        self.assertEqual(etape['motif_omission'], '')
        self.assertGreater(etape['perte_kwh'], 0.0)
        self.assertAlmostEqual(etape['perte_pct'],
                               etape['entree']['pct_energie'], places=2)

    def test_une_chaine_sans_fenetre_omet_l_etape(self):
        _, cascade = appliquer_chaine(SERIE, {})
        etape = next(e for e in cascade['etapes']
                     if e['etape'] == 'indisponibilite')
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])


if __name__ == '__main__':
    unittest.main()
