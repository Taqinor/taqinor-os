"""CALX281 — flux de trésorerie, VAN, TRI et retour actualisé (``economie.py``).

Ce qui est prouvé (le « Done » de CALX281) :

* 100 000 MAD investis, 12 000 MAD/an, indexation 0, dégradation 0,
  actualisation 0, sur un horizon de 10 ans SAISI ⇒ ``retour_ans == 9`` et
  ``van_mad == 20000`` ± 1 ;
* actualisation 5 % ⇒ ``retour_actualise_ans > retour_ans`` sur le cas de
  référence, et ``>=`` sur toute une grille (test de propriété — l'égalité
  est possible quand la marge de l'année de retour absorbe l'actualisation) ;
* taux d'actualisation absent ⇒ ``van_mad is None`` et ``omissions`` nomme
  ``taux_actualisation_pct`` ;
* flux sans changement de signe ⇒ ``tri_pct is None``, jamais une valeur ;
* sans horizon SAISI, aucun flux : tous les indicateurs ``None`` et motivés ;
* chaque grandeur fournie est une hypothèse SOURCÉE, chaque absente une
  omission, jamais les deux ;
* les remplacements : trois modes SAISIS, aucun par défaut ; sans entrée,
  aucun n'est porté au flux et l'omission est publiée ; une entrée incomplète
  est refusée en NOMMANT le champ ;
* la VAN et le TRI relisent ``_npv``/``_irr`` de ``solar_design`` (une seule
  arithmétique) ;
* la sortie a EXACTEMENT les clés du contrat CALX280.

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python -m pytest apps/ventes/tests/test_calx281_flux_van_tri.py -q
"""
import itertools
import json
import unittest
from pathlib import Path

from apps.ventes import economie, solar_design
from apps.ventes.economie import EconomieInvalide, flux_de_tresorerie

CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'ventes_economie.json')


def reference(**surcharges):
    """Le cas de référence de CALX281, surchargeable."""
    params = dict(investissement_mad=100000, economie_annee1_mad=12000,
                  production_annee1_kwh=10000, horizon_ans=10,
                  taux_actualisation_pct=0, indexation_pct=0,
                  degradation_pct=0)
    params.update(surcharges)
    return flux_de_tresorerie(**params)


def cles_omises(bloc):
    return {o['cle'] for o in bloc['omissions']}


def cles_retenues(bloc):
    return {h['cle'] for h in bloc['hypotheses']}


class CasDeReferenceTest(unittest.TestCase):
    def test_retour_en_annee_9_et_van_20000(self):
        bloc = reference()
        self.assertEqual(bloc['retour_ans'], 9)
        self.assertAlmostEqual(bloc['van_mad'], 20000, delta=1)
        self.assertEqual(bloc['horizon_ans'], 10)
        self.assertEqual(len(bloc['flux']), 11)
        self.assertEqual(bloc['flux'][0]['flux_mad'], -100000.0)
        self.assertEqual(bloc['flux'][9]['cumul_mad'], 8000.0)
        # Actualisation nulle : le retour actualisé égale le retour simple.
        self.assertEqual(bloc['retour_actualise_ans'], 9)

    def test_la_sortie_porte_exactement_les_cles_du_contrat(self):
        exemple = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
        bloc = reference()
        self.assertEqual(set(bloc), set(exemple))
        self.assertEqual(set(bloc['flux'][0]), set(exemple['flux'][0]))
        for hypothese in bloc['hypotheses']:
            self.assertEqual(set(hypothese), set(exemple['hypotheses'][0]))
        for omission in bloc['omissions']:
            self.assertEqual(set(omission), set(exemple['omissions'][0]))

    def test_le_flux_rejoue_l_exemple_committe(self):
        """Le flux de l'exemple du contrat EST le cas de référence."""
        exemple = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
        bloc = reference()
        self.assertEqual(bloc['flux'], exemple['flux'])
        for cle in ('van_mad', 'tri_pct', 'lcoe_mad_kwh', 'retour_ans',
                    'retour_actualise_ans'):
            self.assertEqual(bloc[cle], exemple[cle], cle)


class ActualisationTest(unittest.TestCase):
    def test_actualisation_5_pct_allonge_le_retour(self):
        bloc = reference(taux_actualisation_pct=5, horizon_ans=20)
        self.assertEqual(bloc['retour_ans'], 9)
        self.assertIsNotNone(bloc['retour_actualise_ans'])
        self.assertGreater(bloc['retour_actualise_ans'], bloc['retour_ans'])

    def test_propriete_le_retour_actualise_n_est_jamais_plus_court(self):
        for investissement, economie1, taux in itertools.product(
                (50000, 100000, 250000), (6000, 12000, 30000), (1, 5, 8)):
            bloc = flux_de_tresorerie(
                investissement_mad=investissement,
                economie_annee1_mad=economie1, horizon_ans=30,
                taux_actualisation_pct=taux)
            simple, actualise = bloc['retour_ans'], bloc['retour_actualise_ans']
            if simple is None or actualise is None:
                continue
            with self.subTest(i=investissement, e=economie1, t=taux):
                self.assertGreaterEqual(actualise, simple)

    def test_sans_taux_la_van_est_omise_et_le_motif_nomme_le_taux(self):
        bloc = reference(taux_actualisation_pct=None)
        self.assertIsNone(bloc['van_mad'])
        self.assertIsNone(bloc['retour_actualise_ans'])
        self.assertIn('taux_actualisation_pct', cles_omises(bloc))
        self.assertNotIn('taux_actualisation_pct', cles_retenues(bloc))
        motif_van = next(o['motif'] for o in bloc['omissions']
                         if o['cle'] == 'van_mad')
        self.assertIn('taux_actualisation_pct', motif_van)
        # Le TRI et le retour simple n'en dépendent pas : ils restent publiés.
        self.assertIsNotNone(bloc['tri_pct'])
        self.assertEqual(bloc['retour_ans'], 9)
        self.assertTrue(all(ligne['flux_actualise_mad'] is None
                            for ligne in bloc['flux']))

    def test_la_van_relit_npv_de_solar_design(self):
        self.assertIs(economie._npv, solar_design._npv)
        self.assertIs(economie._irr, solar_design._irr)
        bloc = reference(taux_actualisation_pct=5)
        flux = [ligne['flux_mad'] for ligne in bloc['flux']]
        self.assertAlmostEqual(bloc['van_mad'], solar_design._npv(0.05, flux),
                               places=2)


class TriTest(unittest.TestCase):
    def test_tri_du_cas_de_reference(self):
        bloc = reference()
        flux = [ligne['flux_mad'] for ligne in bloc['flux']]
        self.assertAlmostEqual(bloc['tri_pct'],
                               solar_design._irr(flux) * 100, places=4)
        # Le TRI annule la VAN.
        self.assertAlmostEqual(
            solar_design._npv(bloc['tri_pct'] / 100, flux), 0, delta=1)

    def test_flux_sans_changement_de_signe_aucun_tri(self):
        bloc = reference(investissement_mad=0)
        self.assertIsNone(bloc['tri_pct'])
        self.assertIn('tri_pct', cles_omises(bloc))
        bloc = reference(economie_annee1_mad=-500)
        self.assertIsNone(bloc['tri_pct'])


class SansFluxTest(unittest.TestCase):
    def test_sans_horizon_saisi_aucun_flux_et_tout_est_motive(self):
        bloc = reference(horizon_ans=None)
        self.assertEqual(bloc['flux'], [])
        self.assertIsNone(bloc['horizon_ans'])
        omises = cles_omises(bloc)
        for cle in economie.INDICATEURS:
            self.assertIsNone(bloc[cle], cle)
            self.assertIn(cle, omises)
        self.assertIn('horizon_ans', omises)

    def test_aucune_entree_rien_n_est_invente(self):
        bloc = flux_de_tresorerie()
        self.assertEqual(bloc['flux'], [])
        self.assertEqual(bloc['hypotheses'], [])
        for cle in ('investissement_mad', 'economie_annee1_mad',
                    'horizon_ans', 'taux_actualisation_pct',
                    'indexation_pct', 'degradation_pct',
                    'charges_annuelles_mad', 'remplacements'):
            self.assertIn(cle, cles_omises(bloc))


class HypothesesTest(unittest.TestCase):
    def test_chaque_grandeur_fournie_est_sourcee_jamais_omise(self):
        bloc = reference(charges_annuelles_mad={
            'valeur': 500, 'source': 'contrat de maintenance n° 12',
            'saisie_le': '2026-09-23'})
        self.assertEqual(cles_retenues(bloc) & cles_omises(bloc), set())
        for hypothese in bloc['hypotheses']:
            self.assertTrue(hypothese['source'].strip())
        charges = next(h for h in bloc['hypotheses']
                       if h['cle'] == 'charges_annuelles_mad')
        self.assertEqual(charges['source'], 'contrat de maintenance n° 12')
        self.assertEqual(charges['saisie_le'], '2026-09-23')
        self.assertEqual(bloc['flux'][1]['flux_mad'], 11500.0)

    def test_une_saisie_sans_source_est_refusee_en_la_nommant(self):
        with self.assertRaises(EconomieInvalide) as refus:
            reference(horizon_ans={'valeur': 10, 'source': ' '})
        self.assertEqual(refus.exception.champ, 'horizon_ans.source')

    def test_valeurs_invalides_refusees_en_nommant_le_champ(self):
        cas = (('horizon_ans', 0), ('horizon_ans', 10.5),
               ('investissement_mad', -1), ('degradation_pct', 100),
               ('taux_actualisation_pct', -100),
               ('indexation_pct', 'beaucoup'))
        for champ, valeur in cas:
            with self.subTest(champ=champ, valeur=valeur):
                with self.assertRaises(EconomieInvalide) as refus:
                    reference(**{champ: valeur})
                self.assertEqual(refus.exception.champ, champ)

    def test_indexation_absente_projection_a_tarif_constant_dite(self):
        bloc = reference(indexation_pct=None)
        motif = next(o['motif'] for o in bloc['omissions']
                     if o['cle'] == 'indexation_pct')
        self.assertIn('tarif constant', motif)
        self.assertEqual({ligne['economie_mad'] for ligne in bloc['flux'][1:]},
                         {12000.0})

    def test_indexation_et_degradation_saisies_portees_au_flux(self):
        bloc = reference(indexation_pct=4, degradation_pct=0.5)
        facteur = 1.04 ** 9 * 0.995 ** 9
        self.assertAlmostEqual(bloc['flux'][10]['economie_mad'],
                               12000 * facteur, places=2)


class RemplacementsTest(unittest.TestCase):
    ONDULEUR = {'equipement': 'onduleur', 'annee': 8, 'mode': 'remplacer',
                'montant_mad': 9000, 'source': 'devis fournisseur n° 77'}

    def test_sans_entree_aucun_remplacement_porte_et_omission_publiee(self):
        bloc = reference()
        self.assertIn('remplacements', cles_omises(bloc))
        self.assertEqual({ligne['flux_mad'] for ligne in bloc['flux'][1:]},
                         {12000.0})

    def test_un_remplacement_saisi_est_retranche_l_annee_dite(self):
        bloc = reference(remplacements=[self.ONDULEUR])
        self.assertEqual(bloc['flux'][8]['flux_mad'], 3000.0)
        self.assertEqual(bloc['flux'][8]['economie_mad'], 12000.0)
        self.assertNotIn('remplacements', cles_omises(bloc))
        hypothese = next(h for h in bloc['hypotheses']
                         if h['cle'] == 'remplacements[0]')
        self.assertIn('devis fournisseur n° 77', hypothese['source'])
        self.assertIn('remplacer', hypothese['source'])
        # 9 000 MAD retranchés : le cumul de l'an 10 perd 9 000 MAD.
        self.assertEqual(bloc['flux'][10]['cumul_mad'], 11000.0)
        self.assertEqual(bloc['retour_ans'], 10)

    def test_retirer_dit_ce_qui_n_est_pas_retranche(self):
        retrait = dict(self.ONDULEUR, mode='retirer', equipement='batterie',
                       montant_mad=0)
        bloc = reference(remplacements=[retrait])
        self.assertIn('remplacements[0].economie_retiree', cles_omises(bloc))

    def test_aucun_mode_par_defaut_et_champs_nommes(self):
        cas = (('mode', None, 'remplacements[0].mode'),
               ('mode', 'jeter', 'remplacements[0].mode'),
               ('source', '', 'remplacements[0].source'),
               ('annee', None, 'remplacements[0].annee'),
               ('annee', 11, 'remplacements[0].annee'),
               ('montant_mad', None, 'remplacements[0].montant_mad'),
               ('montant_mad', -5, 'remplacements[0].montant_mad'),
               ('equipement', ' ', 'remplacements[0].equipement'))
        for cle, valeur, champ in cas:
            with self.subTest(cle=cle, valeur=valeur):
                entree = dict(self.ONDULEUR, **{cle: valeur})
                with self.assertRaises(EconomieInvalide) as refus:
                    reference(remplacements=[entree])
                self.assertEqual(refus.exception.champ, champ)


class RetourPlafonneTest(unittest.TestCase):
    def test_retour_au_dela_de_30_ans_non_publie(self):
        bloc = flux_de_tresorerie(investissement_mad=100000,
                                  economie_annee1_mad=3000, horizon_ans=40)
        # Retour réel en année 34 : au-delà du plafond de 30 ans.
        self.assertIsNone(bloc['retour_ans'])
        motif = next(o['motif'] for o in bloc['omissions']
                     if o['cle'] == 'retour_ans')
        self.assertIn('30 ans', motif)

    def test_retour_non_atteint_sur_l_horizon(self):
        bloc = flux_de_tresorerie(investissement_mad=100000,
                                  economie_annee1_mad=5000, horizon_ans=10)
        self.assertIsNone(bloc['retour_ans'])
        self.assertIn('retour_ans', cles_omises(bloc))


class AucuneCleInterditeTest(unittest.TestCase):
    def test_aucune_cle_prix_cout_marge(self):
        bloc = reference(remplacements=[RemplacementsTest.ONDULEUR],
                         charges_annuelles_mad=300)

        def cles(noeud):
            if isinstance(noeud, dict):
                for cle, valeur in noeud.items():
                    yield str(cle)
                    yield from cles(valeur)
            elif isinstance(noeud, list):
                for valeur in noeud:
                    yield from cles(valeur)

        for cle in cles(bloc):
            for mot in ('prix', 'cout', 'marge'):
                self.assertNotIn(mot, cle.lower(), cle)


if __name__ == '__main__':
    unittest.main()
