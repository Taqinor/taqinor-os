"""CALX175 — les auxiliaires sont une énergie soutirée, pas un pourcentage.

Aucune base, aucun réseau : quatre heures alternatives (deux de production,
deux de nuit) et des puissances saisies avec leur provenance.

Run :
    python manage.py test apps.calepinage.tests.test_calx175_auxiliaires
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import auxiliaires

#: Deux heures à 2 et 3 kW, puis deux heures de nuit : 5 kWh alternatifs.
SERIE = {
    'pas_minutes': 60,
    'colonne_energie': 'p_ac_kw',
    'points': [
        {'mois': 6, 'heure': 10, 'p_ac_kw': 2.0},
        {'mois': 6, 'heure': 12, 'p_ac_kw': 3.0},
        {'mois': 6, 'heure': 22, 'p_ac_kw': 0.0},
        {'mois': 6, 'heure': 23, 'p_ac_kw': 0.0},
    ],
}


def saisie(valeur):
    return {'valeur': valeur, 'source': 'societe',
            'reference': 'Relevé de l’installation (essai)'}


def contexte(constante=50.0, par_kw=10.0, nuit=8.0, **extras):
    reglages = {}
    if constante is not None:
        reglages[auxiliaires.CLE_CONSTANTE] = saisie(constante)
    if par_kw is not None:
        reglages[auxiliaires.CLE_PAR_KW] = saisie(par_kw)
    if nuit is not None:
        reglages[auxiliaires.CLE_NUIT] = saisie(nuit)
    base = {'reglages_simulation': reglages, 'postes_saisis': [],
            'fiche_onduleur': {}, 'electrique': {}}
    base.update(extras)
    return base


class EnergieSoutireeTest(unittest.TestCase):

    def setUp(self):
        self.serie, self.etape = auxiliaires.appliquer(SERIE, contexte())
        self.entree = self.etape['entree']

    def test_l_etape_s_applique_et_cite_pvsyst(self):
        self.assertEqual(self.etape['motif_omission'], '')
        self.assertEqual(self.etape['source'], 'societe')
        self.assertIn('PVsyst', self.etape['reference'])

    def test_l_energie_de_jour_suit_les_deux_termes(self):
        # 50 + 10 × 2 = 70 W ; 50 + 10 × 3 = 80 W.
        self.assertAlmostEqual(self.entree['energie_jour_kwh'], 0.150,
                               places=6)

    def test_l_energie_de_nuit_est_strictement_positive(self):
        self.assertEqual(self.entree['heures_de_nuit'], 2)
        self.assertGreater(self.entree['energie_nuit_kwh'], 0.0)
        self.assertAlmostEqual(self.entree['energie_nuit_kwh'], 0.016,
                               places=6)

    def test_la_nuit_la_puissance_devient_negative(self):
        self.assertAlmostEqual(self.serie['points'][2]['p_ac_kw'], -0.008,
                               places=9)

    def test_l_energie_de_la_serie_baisse_du_total(self):
        self.assertAlmostEqual(etapes.energie_kwh(self.serie),
                               5.0 - 0.166, places=6)
        self.assertEqual(etapes.energie_kwh(SERIE), 5.0)

    def test_le_pourcentage_publie_est_un_rapport_calcule(self):
        attendu = 100.0 * self.entree['energie_totale_kwh'] / 5.0
        self.assertAlmostEqual(self.entree['pct_publie'], attendu, places=4)
        self.assertAlmostEqual(self.entree['pct_publie'], 3.32, places=4)

    def test_chaque_terme_publie_sa_provenance(self):
        self.assertEqual(self.entree['w_constants']['valeur'], 50.0)
        self.assertEqual(self.entree['w_constants']['source'], 'societe')
        self.assertIn(auxiliaires.CLE_PAR_KW,
                      self.entree['w_par_kw']['origine'])


class NuitSeuleTest(unittest.TestCase):
    """Production nulle et puissance nocturne saisie : l'énergie retirée
    est strictement positive."""

    def setUp(self):
        self.nuit = {'pas_minutes': 60, 'colonne_energie': 'p_ac_kw',
                     'points': [{'heure': 22, 'p_ac_kw': 0.0},
                                {'heure': 23, 'p_ac_kw': 0.0}]}
        self.serie, self.etape = auxiliaires.appliquer(
            self.nuit, contexte(constante=None, par_kw=None, nuit=8.0))

    def test_l_energie_retiree_est_strictement_positive(self):
        self.assertGreater(self.etape['entree']['energie_nuit_kwh'], 0.0)
        self.assertLess(etapes.energie_kwh(self.serie), 0.0)

    def test_le_pourcentage_est_null_faute_de_production(self):
        self.assertIsNone(self.etape['entree']['pct_publie'])


class ConsommationDeNuitDeLaFicheTest(unittest.TestCase):
    """La fiche prime quand le nombre d'onduleurs est connu."""

    def test_la_fiche_est_retenue_et_multipliee(self):
        _, etape = auxiliaires.appliquer(
            SERIE,
            contexte(nuit=None,
                     fiche_onduleur={'conso_nuit_w': 5.0},
                     electrique={'onduleurs': [{'nombre': 2}]}))
        self.assertEqual(etape['entree']['w_nuit']['valeur'], 10.0)
        self.assertEqual(etape['entree']['w_nuit']['source'], 'fiche')

    def test_sans_nombre_d_onduleurs_la_saisie_reprend_la_main(self):
        _, etape = auxiliaires.appliquer(
            SERIE,
            contexte(nuit=8.0, fiche_onduleur={'conso_nuit_w': 5.0}))
        self.assertEqual(etape['entree']['w_nuit']['valeur'], 8.0)
        self.assertEqual(etape['entree']['w_nuit']['source'], 'societe')


class OmissionsNommeesTest(unittest.TestCase):

    def test_aucune_puissance_saisie_omet_en_nommant_les_trois_champs(self):
        serie, etape = auxiliaires.appliquer(
            SERIE, contexte(constante=None, par_kw=None, nuit=None))
        for cle in (auxiliaires.CLE_CONSTANTE, auxiliaires.CLE_PAR_KW,
                    auxiliaires.CLE_NUIT):
            self.assertIn(cle, etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 5.0)

    def test_une_saisie_sans_source_ne_compte_pas(self):
        sans = {'valeur': 50.0, 'source': '', 'reference': ''}
        _, etape = auxiliaires.appliquer(
            SERIE,
            contexte(constante=None, par_kw=None, nuit=None,
                     reglages_simulation={
                         auxiliaires.CLE_CONSTANTE: sans}))
        self.assertTrue(etape['motif_omission'])

    def test_serie_encore_continue_est_omise(self):
        continue_ = {'pas_minutes': 60, 'colonne_energie': 'p_dc_kw',
                     'points': [{'p_dc_kw': 1.0}]}
        serie, etape = auxiliaires.appliquer(continue_, contexte())
        self.assertIn('alternative', etape['motif_omission'])
        self.assertEqual(etapes.energie_kwh(serie), 1.0)


class DansLaCascadeTest(unittest.TestCase):

    def test_le_poste_saisi_est_ecarte_et_non_soustrait_deux_fois(self):
        ctx = contexte(postes_saisis=[{'poste': 'auxiliaires', 'pct': 1.0,
                                       'source': 'societe'}])
        _, cascade = appliquer_chaine(SERIE, ctx)
        ligne = _ligne(cascade, 'auxiliaires')
        # La perte publiée est CELLE DU CALCUL, rapportée à l'énergie que
        # l'étape a réellement reçue — pas la saisie de 1 %, et pas un
        # chiffre figé qu'une étape amont ferait dériver.
        calculee = ligne['entree']['champ']['energie_totale_kwh']
        self.assertAlmostEqual(ligne['perte_pct'],
                               100.0 * calculee / ligne['kwh_avant'],
                               places=2)
        self.assertNotAlmostEqual(ligne['perte_pct'], 1.0, places=2)
        ecartee = ligne['entree']['saisie_ecartee']
        self.assertEqual(ecartee['poste'], 'auxiliaires')
        self.assertTrue(ecartee['motif'])


def _ligne(cascade, nom):
    for etape in cascade['etapes']:
        if etape['etape'] == nom:
            return etape
    raise AssertionError('étape « %s » absente de la cascade' % nom)
