"""AOF124 — la bibliothèque de prix propose 2 950/U depuis l'historique réel.

    python -m unittest apps.ao.tests.test_bibliotheque_prix -v
"""
import unittest
from datetime import date
from decimal import Decimal

from apps.ao.fabrique import bibliotheque_prix as bib


def historique():
    """Les PU réellement pratiqués, du plus ancien au plus récent."""
    return [
        {'reference': 'MOD-625', 'famille': 'modules', 'unite': 'U',
         'prix_unitaire': '2800', 'date': '2025-11-12',
         'dossier': 'AO-202511-0003', 'source': bib.SOURCE_AO},
        {'reference': 'MOD-625', 'famille': 'modules', 'unite': 'U',
         'prix_unitaire': '2900', 'date': '2026-03-04',
         'dossier': 'DV-202603-0011', 'source': bib.SOURCE_DEVIS},
        {'reference': 'MOD-625', 'famille': 'modules', 'unite': 'U',
         'prix_unitaire': '2950', 'date': '2026-07-27',
         'dossier': 'AO-202607-0002', 'source': bib.SOURCE_AO,
         'ecart_moins_disant': '-4.2'},
        {'reference': 'OND-110', 'famille': 'onduleurs', 'unite': 'U',
         'prix_unitaire': '78000', 'date': '2026-07-27',
         'dossier': 'AO-202607-0002', 'source': bib.SOURCE_AO},
        {'reference': 'OND-100', 'famille': 'onduleurs', 'unite': 'U',
         'prix_unitaire': '72000', 'date': '2026-02-01',
         'dossier': 'AO-202602-0001', 'source': bib.SOURCE_AO},
        {'reference': 'BAT-LFP', 'famille': 'batteries', 'unite': 'kWh',
         'prix_unitaire': '2600', 'date': '2026-07-27',
         'dossier': 'AO-202607-0002', 'source': bib.SOURCE_AO},
    ]


class TestProposition(unittest.TestCase):

    def test_le_dernier_ao_depose_propose_2950(self):
        proposition = bib.proposer(historique(), reference='MOD-625')
        self.assertEqual(proposition.prix_unitaire, Decimal('2950'))
        self.assertEqual(proposition.unite, 'U')

    def test_la_proposition_porte_sa_date_et_son_dossier(self):
        proposition = bib.proposer(historique(), reference='MOD-625')
        self.assertEqual(proposition.date, date(2026, 7, 27))
        self.assertEqual(proposition.dossier, 'AO-202607-0002')
        self.assertEqual(proposition.source, bib.SOURCE_AO)
        self.assertEqual(proposition.nb_observations, 3)

    def test_la_justification_est_generee(self):
        justification = bib.proposer(historique(),
                                     reference='MOD-625').justification
        self.assertIn('2 950,00 DH', justification)
        self.assertIn('27/07/2026', justification)
        self.assertIn('AO-202607-0002', justification)

    def test_ecart_au_moins_disant_repris(self):
        self.assertEqual(
            bib.proposer(historique(), reference='MOD-625').ecart_moins_disant,
            Decimal('-4.2'))

    def test_repli_sur_la_mediane_de_la_famille(self):
        proposition = bib.proposer(historique(), reference='OND-XXX',
                                   famille='onduleurs')
        self.assertEqual(proposition.prix_unitaire, Decimal('75000.00'))
        self.assertEqual(proposition.methode, 'médiane de la famille')

    def test_aucune_proposition_sans_historique(self):
        self.assertIsNone(bib.proposer([], reference='MOD-625'))
        self.assertIsNone(bib.proposer(historique(), reference='INCONNU'))

    def test_observation_sans_date_ne_prime_pas_sur_une_datee(self):
        avec_orpheline = historique() + [
            {'reference': 'MOD-625', 'famille': 'modules',
             'prix_unitaire': '9999', 'dossier': 'sans date'}]
        self.assertEqual(
            bib.proposer(avec_orpheline, reference='MOD-625').prix_unitaire,
            Decimal('2950'))

    def test_serialisation(self):
        d = bib.proposer(historique(), reference='MOD-625').vers_dict()
        self.assertEqual(d['prix_unitaire'], '2950')
        self.assertEqual(d['dossier'], 'AO-202607-0002')


class TestAucuneDonneeDeCout(unittest.TestCase):

    def test_une_observation_portant_un_prix_achat_est_refusee(self):
        pollue = historique()
        pollue[0]['prix_achat'] = '2100'
        with self.assertRaises(bib.ObservationInvalide):
            bib.proposer(pollue, reference='MOD-625')

    def test_une_observation_portant_une_marge_est_refusee(self):
        pollue = historique()
        pollue[0]['taux_marge'] = '36'
        with self.assertRaises(bib.ObservationInvalide):
            bib.fourchettes(pollue)

    def test_le_payload_ne_contient_aucun_champ_de_cout(self):
        charge = repr(bib.proposer(historique(),
                                   reference='MOD-625').vers_dict())
        for interdit in ('prix_achat', 'cout', 'marge', 'benefice'):
            self.assertNotIn(interdit, charge.lower(), interdit)


class TestFourchettes(unittest.TestCase):

    def test_une_bande_par_famille(self):
        bandes = bib.fourchettes(historique())
        self.assertEqual(sorted(bandes), ['batteries', 'modules',
                                          'onduleurs'])

    def test_la_bande_encadre_les_prix_observes(self):
        bande = bib.fourchettes(historique())['modules']
        self.assertTrue(bande.contient(Decimal('2950')))
        self.assertTrue(bande.contient(Decimal('2800')))
        self.assertEqual(bande.mediane, Decimal('2900.00'))

    def test_la_bande_publie_sa_fiabilite_et_sa_source(self):
        bandes = bib.fourchettes(historique())
        self.assertTrue(bandes['modules'].fiable)      # 3 observations
        self.assertFalse(bandes['batteries'].fiable)   # 1 observation
        self.assertIn('AO-202607-0002', bandes['batteries'].libelle_source)

    def test_un_prix_aberrant_sort_de_la_bande(self):
        bande = bib.fourchettes(historique())['modules']
        self.assertFalse(bande.contient(Decimal('9000')))
        self.assertFalse(bande.contient(Decimal('500')))

    def test_serialisation_de_la_bande(self):
        d = bib.fourchettes(historique())['modules'].vers_dict()
        self.assertEqual(d['nb_observations'], 3)
        self.assertIs(d['fiable'], True)


class TestHorsBande(unittest.TestCase):

    def lignes(self):
        return [
            {'cle': 'mod', 'famille': 'modules', 'quantite': 560,
             'prix_unitaire': Decimal('2950')},
            {'cle': 'ond', 'famille': 'onduleurs', 'quantite': 10,
             'prix_unitaire': Decimal('150000')},
            {'cle': 'bat', 'famille': 'batteries', 'quantite': 289,
             'prix_unitaire': Decimal('600')},
        ]

    def test_les_lignes_dans_leur_bande_ne_remontent_pas(self):
        ecarts = bib.hors_bande(self.lignes(), bib.fourchettes(historique()))
        self.assertNotIn('mod', [e['cle'] for e in ecarts])

    def test_le_rapport_est_trie_par_impact(self):
        ecarts = bib.hors_bande(self.lignes(), bib.fourchettes(historique()))
        self.assertEqual([e['cle'] for e in ecarts], ['ond', 'bat'])
        self.assertGreater(abs(ecarts[0]['impact']), abs(ecarts[1]['impact']))

    def test_chaque_ecart_porte_sa_bande_et_sa_source(self):
        ecart = bib.hors_bande(self.lignes(),
                               bib.fourchettes(historique()))[0]
        self.assertIn('bas', ecart)
        self.assertIn('haut', ecart)
        self.assertIn('observation', ecart['source'])

    def test_une_famille_sans_historique_ne_declenche_rien(self):
        lignes = [{'cle': 'x', 'famille': 'inconnue', 'quantite': 1,
                   'prix_unitaire': Decimal('1')}]
        self.assertEqual(bib.hors_bande(lignes,
                                        bib.fourchettes(historique())), ())


class TestMediane(unittest.TestCase):

    def test_impair(self):
        self.assertEqual(bib.mediane([Decimal('1'), Decimal('3'),
                                      Decimal('2')]), Decimal('2.00'))

    def test_pair(self):
        self.assertEqual(bib.mediane([Decimal('2'), Decimal('4')]),
                         Decimal('3.00'))

    def test_vide(self):
        self.assertIsNone(bib.mediane([]))


if __name__ == '__main__':
    unittest.main()
