"""CALX167 — l'étape « mismatch fabricant » ne retranche que ce qui est saisi.

Aucune base, aucun réseau : une série de quatre heures, un contexte construit
à la main, et l'ordonnanceur de CALX147 pour vérifier que la cascade reste
continue.

Run :
    python manage.py test apps.calepinage.tests.test_calx167_mismatch_fabricant
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import appliquer_chaine
from apps.calepinage.services.etapes import mismatch_fabricant

SERIE = {
    'pas_minutes': 60,
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 9, 'p_w': 1000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 10, 'p_w': 2000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11, 'p_w': 3000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12, 'p_w': 4000.0},
    ],
}

#: Une dispersion saisie ET sourcée — chiffre d'essai assumé, il ne sort pas
#: de ce fichier.
SAISIE = {'valeur': 2.5, 'source': 'societe',
          'reference': 'Lot de modules mesuré en atelier (essai)'}


def contexte(**extras):
    base = {'reglages_simulation': {}, 'postes_saisis': []}
    base.update(extras)
    return base


def avec_saisie(**extras):
    return contexte(
        reglages_simulation={mismatch_fabricant.CLE_REGLAGE: dict(SAISIE)},
        **extras)


class OmissionTest(unittest.TestCase):
    """Rien de saisi : la série ressort INTACTE, et le motif nomme la clé."""

    def setUp(self):
        self.serie, self.etape = mismatch_fabricant.appliquer(
            SERIE, contexte())

    def test_energie_inchangee(self):
        self.assertEqual(etapes.energie_kwh(self.serie),
                         etapes.energie_kwh(SERIE))

    def test_motif_nomme_la_cle_manquante(self):
        self.assertTrue(self.etape['motif_omission'])
        self.assertIn(mismatch_fabricant.CLE_REGLAGE,
                      self.etape['motif_omission'])

    def test_aucun_forfait_applique(self):
        """Ni source, ni entrée, ni chiffre : une omission ne retranche rien."""
        self.assertIsNone(self.etape['source'])
        self.assertIsNone(self.etape['entree'])
        self.assertIsNone(self.etape['reference'])

    def test_dans_la_cascade_la_ligne_reste_a_null(self):
        _, cascade = appliquer_chaine(SERIE, contexte())
        ligne = _ligne(cascade, 'mismatch_fabricant')
        self.assertIsNone(ligne['kwh_apres'])
        self.assertIsNone(ligne['perte_pct'])
        self.assertTrue(ligne['motif_omission'])


class SaisieSourceeTest(unittest.TestCase):
    """La valeur publiée porte la source SAISIE, jamais une hypothèse."""

    def setUp(self):
        self.serie, self.etape = mismatch_fabricant.appliquer(
            SERIE, avec_saisie())

    def test_la_source_est_celle_de_la_saisie(self):
        self.assertEqual(self.etape['source'], 'societe')
        self.assertNotEqual(self.etape['source'], 'hypothese')

    def test_la_reference_saisie_est_republiee(self):
        self.assertEqual(self.etape['reference'], SAISIE['reference'])

    def test_l_entree_nomme_le_champ_et_le_pourcentage(self):
        self.assertEqual(self.etape['entree']['champ'],
                         mismatch_fabricant.ENTREE_REGLAGE)
        self.assertEqual(self.etape['entree']['pct'], 2.5)

    def test_l_energie_baisse_du_pourcentage_saisi(self):
        self.assertAlmostEqual(etapes.energie_kwh(self.serie),
                               10.0 * (1.0 - 0.025), places=9)

    def test_la_serie_d_entree_n_est_pas_modifiee(self):
        self.assertEqual(etapes.energie_kwh(SERIE), 10.0)

    def test_valeur_sans_source_ne_s_applique_pas(self):
        sans = {'valeur': 2.5, 'source': '', 'reference': ''}
        _, etape = mismatch_fabricant.appliquer(
            SERIE,
            contexte(reglages_simulation={
                mismatch_fabricant.CLE_REGLAGE: sans}))
        self.assertTrue(etape['motif_omission'])


class ArbitrageAvecLePosteSaisiTest(unittest.TestCase):
    """Une saisie du catalogue identique NE se soustrait PAS une 2e fois."""

    def setUp(self):
        self.contexte = avec_saisie(postes_saisis=[
            {'poste': 'mismatch', 'pct': 2.5, 'source': 'societe',
             'libelle': 'Mismatch'}])
        self.serie, self.cascade = appliquer_chaine(SERIE, self.contexte)
        self.ligne = _ligne(self.cascade, 'mismatch_fabricant')

    def test_une_seule_soustraction(self):
        self.assertAlmostEqual(self.ligne['perte_pct'], 2.5, places=3)

    def test_la_saisie_est_publiee_ecartee(self):
        ecartee = self.ligne['entree']['saisie_ecartee']
        self.assertEqual(ecartee['poste'], 'mismatch')
        self.assertEqual(ecartee['etape'], 'mismatch_fabricant')
        self.assertTrue(ecartee['motif'])

    def test_le_calcul_reste_celui_de_l_etape(self):
        self.assertEqual(self.ligne['entree']['champ']['champ'],
                         mismatch_fabricant.ENTREE_REGLAGE)


class SuiviParModuleTest(unittest.TestCase):
    """Micro-onduleur : 0,0 % PUBLIÉ avec sa raison, saisie ou pas."""

    def setUp(self):
        self.contexte = avec_saisie(
            **{mismatch_fabricant.CLE_SUIVI_MPP: 'micro_onduleur'})
        self.serie, self.etape = mismatch_fabricant.appliquer(
            SERIE, self.contexte)

    def test_zero_pour_cent_et_energie_intacte(self):
        self.assertEqual(self.etape['entree']['pct'], 0.0)
        self.assertEqual(etapes.energie_kwh(self.serie), 10.0)

    def test_la_raison_est_publiee(self):
        self.assertIn('micro-onduleur', self.etape['entree']['motif'])
        self.assertFalse(self.etape['motif_omission'])

    def test_la_reference_est_celle_d_aurora(self):
        self.assertIn('Aurora', self.etape['reference'])

    def test_la_cascade_publie_une_perte_nulle_et_non_null(self):
        _, cascade = appliquer_chaine(SERIE, self.contexte)
        ligne = _ligne(cascade, 'mismatch_fabricant')
        self.assertEqual(ligne['perte_pct'], 0.0)
        self.assertEqual(ligne['kwh_avant'], ligne['kwh_apres'])

    def test_un_optimiseur_au_materiel_vaut_la_meme_declaration(self):
        _, etape = mismatch_fabricant.appliquer(
            SERIE, avec_saisie(materiel={'optimiseur': {'pmax_in_w': 600}}))
        self.assertEqual(etape['entree']['pct'], 0.0)
        self.assertIn('optimiseur', etape['entree']['motif'])


class MemeOrigineQueLOmbrageTest(unittest.TestCase):
    """CALX168 tire du même chiffre : l'étape refuse de s'exécuter."""

    def setUp(self):
        self.serie, self.etape = mismatch_fabricant.appliquer(
            SERIE,
            avec_saisie(**{mismatch_fabricant.CLE_MISMATCH_OMBRAGE: {
                'origine': mismatch_fabricant.ENTREE_REGLAGE}}))

    def test_omise_en_nommant_les_deux_etapes(self):
        self.assertTrue(self.etape['motif_omission'])
        self.assertIn('mismatch_ombrage', self.etape['motif_omission'])

    def test_energie_intacte(self):
        self.assertEqual(etapes.energie_kwh(self.serie), 10.0)

    def test_une_autre_origine_ne_bloque_rien(self):
        _, etape = mismatch_fabricant.appliquer(
            SERIE,
            avec_saisie(**{mismatch_fabricant.CLE_MISMATCH_OMBRAGE: {
                'origine': 'courbes_iv_par_chaine'}}))
        self.assertFalse(etape['motif_omission'])


def _ligne(cascade, nom):
    for etape in cascade['etapes']:
        if etape['etape'] == nom:
            return etape
    raise AssertionError('étape « %s » absente de la cascade' % nom)
