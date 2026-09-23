"""CALX290 — comparer deux scénarios sur le MÊME flux (``economie.py``).

Ce qui est prouvé (le « Done » de CALX290) :

* deux scénarios identiques ⇒ écarts tous nuls (test de propriété, sur une
  grille) ;
* scénarios à horizons différents ⇒ refus nommant ``scenarios[1].horizon_ans``
  — et la PREMIÈRE divergence est nommée (taux, indexation) ;
* cinq scénarios ⇒ refus nommant ``scenarios`` ;
* aucun scénario ne porte de clé ``prix``/``cout``/``marge`` — ni en sortie,
  ni en entrée (clé inconnue refusée en la nommant) ;
* les indicateurs de chaque scénario sont ceux du flux de CALX281, et
  l'écart est ``scénario − référence``.

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python -m pytest apps/ventes/tests/test_calx290_comparaison_scenarios.py -q
"""
import itertools
import unittest

from apps.ventes.economie import (INDICATEURS, EconomieInvalide,
                                  comparer_scenarios, flux_de_tresorerie)

FINANCE = dict(horizon_ans=20, taux_actualisation_pct=5, indexation_pct=0)


def scenario(nom, **surcharges):
    donnees = dict(nom=nom, production_annuelle_kwh=10000,
                   economie_annee1_mad=12000, investissement_mad=100000,
                   **FINANCE)
    donnees.update(surcharges)
    return donnees


def cles(noeud):
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield str(cle)
            yield from cles(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from cles(valeur)


class EcartsTest(unittest.TestCase):
    def test_propriete_deux_scenarios_identiques_ecarts_nuls(self):
        for investissement, economie1, production in itertools.product(
                (60000, 100000), (9000, 12000), (8000, 10000)):
            donnees = dict(investissement_mad=investissement,
                           economie_annee1_mad=economie1,
                           production_annuelle_kwh=production)
            resultat = comparer_scenarios([scenario('A', **donnees),
                                           scenario('B', **donnees)])
            ecarts = resultat['scenarios'][1]['ecarts']
            with self.subTest(i=investissement, e=economie1, p=production):
                self.assertEqual(set(ecarts), set(INDICATEURS))
                for cle, ecart in ecarts.items():
                    self.assertEqual(ecart, 0, cle)

    def test_indicateurs_et_ecarts_du_meme_flux(self):
        resultat = comparer_scenarios([
            scenario('Sans batterie'),
            scenario('Avec batterie', investissement_mad=130000,
                     economie_annee1_mad=15000)])
        self.assertEqual(resultat['reference'], 'Sans batterie')
        sans, avec = resultat['scenarios']
        attendu = flux_de_tresorerie(
            investissement_mad=130000, economie_annee1_mad=15000,
            production_annee1_kwh=10000, **FINANCE)
        for cle in INDICATEURS:
            self.assertEqual(avec[cle], attendu[cle], cle)
        self.assertAlmostEqual(avec['ecarts']['van_mad'],
                               avec['van_mad'] - sans['van_mad'], places=2)
        self.assertEqual(avec['ecarts']['retour_ans'],
                         avec['retour_ans'] - sans['retour_ans'])
        self.assertEqual(set(sans['ecarts'].values()), {0})

    def test_indicateur_non_publie_ecart_non_publie(self):
        resultat = comparer_scenarios([
            scenario('A'), scenario('B', production_annuelle_kwh=None)])
        self.assertIsNone(resultat['scenarios'][1]['lcoe_mad_kwh'])
        self.assertIsNone(resultat['scenarios'][1]['ecarts']['lcoe_mad_kwh'])
        self.assertIn('scenarios[1].lcoe_mad_kwh',
                      {o['cle'] for o in resultat['omissions']})


class RefusTest(unittest.TestCase):
    def test_horizons_differents_refus_nommant_le_second(self):
        with self.assertRaises(EconomieInvalide) as refus:
            comparer_scenarios([scenario('A'),
                                scenario('B', horizon_ans=25)])
        self.assertEqual(refus.exception.champ, 'scenarios[1].horizon_ans')

    def test_la_premiere_divergence_est_nommee(self):
        cas = ((dict(taux_actualisation_pct=6), 'scenarios[1].taux_actualisation_pct'),
               (dict(indexation_pct=2), 'scenarios[1].indexation_pct'),
               (dict(horizon_ans=25, taux_actualisation_pct=6),
                'scenarios[1].horizon_ans'))
        for divergence, champ in cas:
            with self.subTest(champ=champ):
                with self.assertRaises(EconomieInvalide) as refus:
                    comparer_scenarios([scenario('A'),
                                        scenario('B', **divergence)])
                self.assertEqual(refus.exception.champ, champ)
        with self.assertRaises(EconomieInvalide) as refus:
            comparer_scenarios([scenario('A'), scenario('B'),
                                scenario('C', indexation_pct=1)])
        self.assertEqual(refus.exception.champ, 'scenarios[2].indexation_pct')

    def test_cinq_scenarios_refus_nommant_scenarios(self):
        with self.assertRaises(EconomieInvalide) as refus:
            comparer_scenarios([scenario(nom) for nom in 'ABCDE'])
        self.assertEqual(refus.exception.champ, 'scenarios')

    def test_un_seul_scenario_n_est_pas_une_comparaison(self):
        with self.assertRaises(EconomieInvalide) as refus:
            comparer_scenarios([scenario('A')])
        self.assertEqual(refus.exception.champ, 'scenarios')

    def test_noms_obligatoires_et_uniques(self):
        for noms, champ in ((('A', ''), 'scenarios[1].nom'),
                            (('A', 'A'), 'scenarios[1].nom')):
            with self.subTest(noms=noms):
                with self.assertRaises(EconomieInvalide) as refus:
                    comparer_scenarios([scenario(nom) for nom in noms])
                self.assertEqual(refus.exception.champ, champ)

    def test_une_cle_prix_en_entree_est_refusee(self):
        with self.assertRaises(EconomieInvalide) as refus:
            comparer_scenarios([scenario('A'),
                                scenario('B', prix_achat=50000)])
        self.assertEqual(refus.exception.champ, 'scenarios[1].prix_achat')

    def test_un_refus_du_flux_est_localise_au_scenario(self):
        with self.assertRaises(EconomieInvalide) as refus:
            comparer_scenarios([scenario('A'),
                                scenario('B', degradation_pct=-1)])
        self.assertEqual(refus.exception.champ, 'scenarios[1].degradation_pct')


class VocabulaireTest(unittest.TestCase):
    def test_aucune_cle_prix_cout_marge_en_sortie(self):
        resultat = comparer_scenarios([
            scenario('A'), scenario('B', charges_annuelles_mad=300),
            scenario('C', remplacements=[{
                'equipement': 'onduleur', 'annee': 10, 'mode': 'remplacer',
                'montant_mad': 7000, 'source': 'devis fournisseur n° 9'}])])
        for cle in cles(resultat):
            for mot in ('prix', 'cout', 'marge'):
                self.assertNotIn(mot, cle.lower(), cle)


if __name__ == '__main__':
    unittest.main()
