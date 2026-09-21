"""CALX166 — le LID suit la TECHNOLOGIE de cellule, ou se tait.

Aucune base, aucun réseau : une série de deux heures, une fiche produit et
une table société en dur.

Run :
    python manage.py test apps.calepinage.tests.test_calx166_lid
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import lid

SERIE = {'pas_minutes': 60,
         'points': [{'p_w': 1000.0}, {'p_w': 3000.0}]}

TABLE = {
    'p-type PERC': {'pct': 1.5, 'source': 'texte',
                    'reference': 'Fiche fournisseur 2026'},
    'N-type TOPCon': {'pct': 0.4, 'source': 'mesure',
                      'reference': 'Mesure atelier'},
}


def contexte_de(*, techno=None, table=None, source='societe'):
    contexte = {}
    if table is not None:
        contexte['reglages_simulation'] = {
            'lid_par_techno': {'valeur': table, 'source': source,
                               'reference': 'Table LID société'}}
    if techno is not None:
        contexte['fiche_module'] = {'techno_cellule': techno}
    return contexte


class OmissionTest(unittest.TestCase):
    """Chaque silence nomme SON champ — jamais un « non calculé » générique."""

    def test_aucune_table_societe_omet_l_etape_en_nommant_la_cle(self):
        rendue, etape = lid.appliquer(SERIE, contexte_de(techno='PERC'))
        self.assertIn('lid_par_techno', etape['motif_omission'])
        self.assertIn('aucune valeur par défaut', etape['motif_omission'])
        self.assertIs(rendue, SERIE)

    def test_une_fiche_sans_techno_omet_l_etape_en_le_disant(self):
        _, etape = lid.appliquer(SERIE, contexte_de(techno='', table=TABLE))
        self.assertIn('techno_cellule', etape['motif_omission'])
        self.assertIsNone(etape['source'])

    def test_une_fiche_absente_omet_l_etape_de_la_meme_facon(self):
        _, etape = lid.appliquer(SERIE, contexte_de(table=TABLE))
        self.assertIn('techno_cellule', etape['motif_omission'])

    def test_une_techno_hors_table_est_omise_en_citant_la_chaine_lue(self):
        _, etape = lid.appliquer(
            SERIE, contexte_de(techno='HJT bifacial', table=TABLE))
        self.assertIn('« HJT bifacial »', etape['motif_omission'])
        self.assertIn('type n', etape['motif_omission'])

    def test_une_ligne_sans_source_est_refusee_en_nommant_la_technologie(self):
        table = dict(TABLE, **{'HJT': {'pct': 0.6}})
        contexte = contexte_de(techno='HJT', table=table)
        _, etape = lid.appliquer(SERIE, contexte)
        self.assertIn('REFUSÉE', etape['motif_omission'])
        self.assertIn('« HJT »', etape['motif_omission'])
        self.assertIn('source', etape['motif_omission'])

    def test_une_ligne_sans_pourcentage_lisible_est_refusee(self):
        table = dict(TABLE, **{'HJT': {'pct': 'un peu', 'source': 'societe'}})
        contexte = contexte_de(techno='HJT', table=table)
        _, etape = lid.appliquer(SERIE, contexte)
        self.assertIn('« HJT »', etape['motif_omission'])
        self.assertIn('pourcentage', etape['motif_omission'])

    def test_la_serie_ressort_intacte_a_chaque_omission(self):
        for contexte in (contexte_de(techno='PERC'),
                         contexte_de(techno='', table=TABLE),
                         contexte_de(techno='HJT bifacial', table=TABLE)):
            rendue, etape = lid.appliquer(SERIE, contexte)
            self.assertTrue(etape['motif_omission'])
            self.assertEqual(etapes.energie_kwh(rendue), 4.0)


class ApplicationTest(unittest.TestCase):
    """La technologie lue choisit la ligne, et la ligne dit sa provenance."""

    def setUp(self):
        self.rendue, self.etape = lid.appliquer(
            SERIE, contexte_de(techno='p-type PERC', table=TABLE))

    def test_la_perte_de_la_ligne_est_appliquee(self):
        self.assertAlmostEqual(etapes.energie_kwh(self.rendue),
                               4.0 * (1 - 0.015), places=9)

    def test_l_entree_dit_la_techno_lue_et_la_ligne_retenue(self):
        self.assertEqual(self.etape['entree']['techno_lue'], 'p-type PERC')
        self.assertEqual(self.etape['entree']['ligne_retenue'],
                         'p-type PERC')
        self.assertEqual(self.etape['entree']['pct'], 1.5)

    def test_la_source_publiee_est_celle_de_la_ligne(self):
        self.assertEqual(self.etape['source'], 'texte')
        self.assertEqual(self.etape['entree']['source_du_reglage'],
                         'societe')

    def test_la_reference_cite_pvsyst(self):
        self.assertIn('PVsyst', self.etape['reference'])
        self.assertIn('type p', self.etape['reference'])

    def test_la_casse_et_la_ponctuation_de_la_fiche_ne_comptent_pas(self):
        _, etape = lid.appliquer(
            SERIE, contexte_de(techno='n_type TOPCON', table=TABLE))
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['ligne_retenue'], 'N-type TOPCon')
        self.assertEqual(etape['entree']['pct'], 0.4)

    def test_la_serie_d_entree_n_est_jamais_modifiee_sur_place(self):
        self.assertEqual(etapes.energie_kwh(SERIE), 4.0)


class DansLaChaineTest(unittest.TestCase):
    """L'étape passe par l'ordonnanceur sans rien lui devoir."""

    def test_l_etape_est_appliquee_et_mesuree(self):
        _, cascade = appliquer_chaine(
            SERIE, contexte_de(techno='p-type PERC', table=TABLE))
        etape = next(e for e in cascade['etapes'] if e['etape'] == 'lid')
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['kwh_avant'], 4.0)
        self.assertAlmostEqual(etape['perte_pct'], 1.5, places=3)

    def test_une_chaine_sans_table_omet_l_etape(self):
        _, cascade = appliquer_chaine(SERIE, {})
        etape = next(e for e in cascade['etapes'] if e['etape'] == 'lid')
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])


if __name__ == '__main__':
    unittest.main()
