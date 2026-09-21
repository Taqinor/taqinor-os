"""AOF126 — un seul texte de clause, deux insertions, identité octet-à-octet.

    python -m unittest apps.ao.tests.test_aof_clause_reserve -v
"""
import unittest

from apps.ao.fabrique import clauses


class TestTexteUnique(unittest.TestCase):

    def test_le_texte_de_reference_est_celui_du_dossier(self):
        texte = clauses.texte_clause()
        self.assertTrue(texte.startswith('Les quantités du présent bordereau'))
        self.assertIn('relevé contradictoire complet des toitures', texte)
        self.assertIn('le marché étant à prix unitaires', texte)
        self.assertTrue(texte.endswith(
            'quantités réellement installées et réceptionnées.'))

    def test_le_texte_societe_prime(self):
        self.assertEqual(clauses.texte_clause(texte_societe='Autre rédaction.'),
                         'Autre rédaction.')

    def test_un_texte_societe_vide_ne_prime_pas(self):
        self.assertEqual(clauses.texte_clause(texte_societe='   '),
                         clauses.CLAUSE_RESERVE_QUANTITES)

    def test_clause_inconnue(self):
        with self.assertRaises(KeyError):
            clauses.texte_clause(code='penalites')

    def test_une_seule_insertion_produit_deux_textes_identiques(self):
        insertions = clauses.inserer(clauses.EMPLACEMENTS_OBLIGATOIRES)
        self.assertEqual(sorted(insertions),
                         sorted(clauses.EMPLACEMENTS_OBLIGATOIRES))
        self.assertEqual(len(set(insertions.values())), 1)


class TestObligation(unittest.TestCase):

    def test_marche_a_prix_unitaires(self):
        for type_prix in ('unitaires', 'PRIX_UNITAIRES', 'bordereau'):
            self.assertTrue(clauses.clause_obligatoire(type_prix), type_prix)

    def test_marche_forfaitaire_non_concerne(self):
        self.assertFalse(clauses.clause_obligatoire('forfaitaire'))
        self.assertFalse(clauses.clause_obligatoire(None))

    def test_un_marche_forfaitaire_passe_la_porte_sans_clause(self):
        self.assertTrue(clauses.exiger({}, type_prix='forfaitaire'))


class TestIdentiteOctetAOctet(unittest.TestCase):

    def occurrences(self, **remplacements):
        base = clauses.inserer(clauses.EMPLACEMENTS_OBLIGATOIRES)
        base.update(remplacements)
        return base

    def test_deux_occurrences_identiques_sont_conformes(self):
        rapport = clauses.controler(self.occurrences())
        self.assertTrue(rapport.conforme)
        self.assertEqual(rapport.motifs(), ())
        self.assertTrue(clauses.exiger(self.occurrences()))

    def test_un_seul_caractere_de_difference_est_detecte(self):
        altere = clauses.CLAUSE_RESERVE_QUANTITES.replace('pourra',
                                                          'pourrait', 1)
        rapport = clauses.controler(self.occurrences(lettre_soumission=altere))
        self.assertFalse(rapport.conforme)
        self.assertEqual(len(rapport.divergences), 1)
        self.assertIn('lettre_soumission', rapport.divergences[0].motif)

    def test_la_position_du_premier_ecart_est_donnee(self):
        """« maximum » → « maximun » : l'écart tombe sur le dernier caractère."""
        reference = clauses.CLAUSE_RESERVE_QUANTITES
        altere = reference.replace('maximum', 'maximun', 1)
        divergence = clauses.controler(
            self.occurrences(lettre_soumission=altere)).divergences[0]
        attendue = reference.index('maximum') + len('maximum')
        self.assertEqual(divergence.position, attendue)
        self.assertIn('maximu', divergence.extrait_a)
        self.assertIn('maximu', divergence.extrait_b)

    def test_un_mot_supprime_est_detecte(self):
        altere = clauses.CLAUSE_RESERVE_QUANTITES.replace(
            'exclusivement ', '', 1)
        self.assertFalse(
            clauses.controler(self.occurrences(bordereau=altere)).conforme)

    def test_une_espace_en_trop_est_detectee(self):
        altere = clauses.CLAUSE_RESERVE_QUANTITES.replace('. L\'étude',
                                                          '.  L\'étude', 1)
        self.assertFalse(
            clauses.controler(self.occurrences(bordereau=altere)).conforme)

    def test_le_depot_est_refuse_sur_divergence(self):
        altere = clauses.CLAUSE_RESERVE_QUANTITES.replace('pourra',
                                                          'pourrait', 1)
        with self.assertRaises(clauses.ClauseDivergente):
            clauses.exiger(self.occurrences(lettre_soumission=altere))

    def test_comparaison_a_une_reference_explicite(self):
        rapport = clauses.controler(self.occurrences(),
                                    reference='Autre texte.')
        self.assertFalse(rapport.conforme)
        self.assertEqual(len(rapport.divergences), 2)


class TestAbsence(unittest.TestCase):

    def test_clause_absente_du_bordereau(self):
        rapport = clauses.controler(
            {'bordereau': '', 'lettre_soumission':
                clauses.CLAUSE_RESERVE_QUANTITES})
        self.assertEqual(rapport.manquantes, ('bordereau',))
        self.assertFalse(rapport.conforme)

    def test_clause_absente_des_deux_pieces(self):
        rapport = clauses.controler({})
        self.assertEqual(rapport.manquantes,
                         clauses.EMPLACEMENTS_OBLIGATOIRES)

    def test_le_depot_est_refuse_sur_absence(self):
        with self.assertRaises(clauses.ClauseAbsente):
            clauses.exiger({'bordereau': clauses.CLAUSE_RESERVE_QUANTITES})

    def test_serialisation_du_rapport(self):
        d = clauses.controler({}).vers_dict()
        self.assertIs(d['conforme'], False)
        self.assertEqual(len(d['motifs']), 2)


class TestDependances(unittest.TestCase):

    def test_les_pieces_dependantes_sont_publiees(self):
        self.assertEqual(clauses.pieces_dependantes(),
                         clauses.EMPLACEMENTS_OBLIGATOIRES)

    def test_un_texte_modifie_touche_les_deux_pieces(self):
        insertions = clauses.inserer(clauses.pieces_dependantes(),
                                     texte_societe='Nouvelle rédaction.')
        self.assertEqual(set(insertions.values()), {'Nouvelle rédaction.'})
        self.assertTrue(clauses.controler(insertions).conforme)


if __name__ == '__main__':
    unittest.main()
