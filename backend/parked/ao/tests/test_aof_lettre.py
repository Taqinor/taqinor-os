"""AOF131 — lettre de soumission : montants et clause identiques au bordereau.

    python -m unittest apps.ao.tests.test_aof_lettre -v
"""
import html as _html
import pathlib
import unittest
from decimal import Decimal

from apps.ao.fabrique import clauses
from apps.ao.fabrique.contexte import construire_contexte, litteraux_chiffres
from apps.ao.fabrique.montants import duree_en_lettres
from apps.ao.fabrique.rendus import bordereau_pdf, lettre
from apps.ao.tests.aof_fixtures import (ARRETE_TTC, TOTAL_HT, TOTAL_TTC, TVA,
                                        bordereau_depose, contexte_dossier,
                                        rendre_gabarit)

GABARITS = pathlib.Path(__file__).resolve().parents[3] / 'templates'


def pieces():
    lignes = bordereau_depose()
    contexte = construire_contexte(contexte_dossier(lignes))
    donnees = lettre.contexte_gabarit(lignes, contexte)
    return lignes, contexte, donnees


def rendu():
    _, contexte, donnees = pieces()
    return _html.unescape(rendre_gabarit(lettre.NOM_GABARIT, donnees)), \
        contexte, donnees


class TestMontantsIdentiquesAuBordereau(unittest.TestCase):

    def setUp(self):
        self.lignes, self.contexte, self.donnees = pieces()

    def test_les_montants_sont_ceux_du_bordereau_au_centime(self):
        valeurs_bordereau = bordereau_pdf.valeurs_de_controle(
            bordereau_pdf.contexte_gabarit(self.lignes, self.contexte))
        self.assertEqual(
            lettre.controler_vs_bordereau(self.donnees, valeurs_bordereau), ())

    def test_les_montants_reels_du_dossier(self):
        portes = lettre.valeurs_de_controle(self.donnees)
        self.assertEqual(portes['total_ht'], TOTAL_HT)
        self.assertEqual(portes['tva'], TVA)
        self.assertEqual(portes['total_ttc'], TOTAL_TTC)

    def test_un_ecart_de_montant_est_detecte(self):
        """Le défaut réel : une lettre et un bordereau qui divergent."""
        faux = {'total_ht': TOTAL_HT, 'tva': TVA,
                'total_ttc': Decimal('5219280')}
        ecarts = lettre.controler_vs_bordereau(self.donnees, faux)
        self.assertEqual(len(ecarts), 1)
        self.assertIn('total_ttc', ecarts[0])

    def test_l_arrete_en_lettres_est_celui_du_montant(self):
        self.assertEqual(self.donnees['total_ttc_lettres'], ARRETE_TTC)


class TestClauseIdentique(unittest.TestCase):

    def test_la_clause_est_identique_a_celle_du_bordereau(self):
        _, _, donnees = pieces()
        rapport = lettre.controler_clause(
            donnees, clauses.CLAUSE_RESERVE_QUANTITES)
        self.assertTrue(rapport.conforme)

    def test_une_divergence_d_un_caractere_est_detectee(self):
        _, _, donnees = pieces()
        altere = clauses.CLAUSE_RESERVE_QUANTITES.replace('pourra',
                                                          'pourrait', 1)
        self.assertFalse(lettre.controler_clause(donnees, altere).conforme)


class TestContenuDeLaLettre(unittest.TestCase):

    def setUp(self):
        self.html, self.contexte, self.donnees = rendu()

    def test_l_identite_du_signataire(self):
        self.assertIn('Reda Kasri', self.html)
        self.assertIn('Gérant', self.html)

    def test_les_mentions_du_marche(self):
        self.assertIn('FRDISI', self.html)
        self.assertIn('AO 12/2026', self.html)
        self.assertIn("appel d'offres ouvert", self.html)

    def test_les_identifiants_legaux(self):
        for mention in ('002345678000091', '123456', '55667788', '9988776'):
            self.assertIn(mention, self.html, mention)

    def test_les_montants_en_chiffres_et_en_lettres(self):
        self.assertIn(self.donnees['total_ttc_texte'], self.html)
        self.assertIn(ARRETE_TTC, self.html)

    def test_la_validite_de_75_jours_en_chiffres_et_en_lettres(self):
        self.assertEqual(self.donnees['validite_jours'], 75)
        self.assertIn('75 jours', self.html)
        self.assertIn(duree_en_lettres(75), self.html)
        self.assertIn('Soixante-quinze jours', self.html)

    def test_le_delai_d_execution_en_lettres(self):
        self.assertIn('Cent vingt jours', self.html)

    def test_la_clause_de_reserve_est_reportee(self):
        self.assertIn(clauses.CLAUSE_RESERVE_QUANTITES, self.html)

    def test_la_date_est_formatee_par_la_fabrique(self):
        self.assertIn('01/08/2026', self.html)
        self.assertNotIn('Aug', self.html)

    def test_l_empreinte_du_contexte_est_imprimee(self):
        self.assertIn(self.contexte['empreinte'], self.html)

    def test_concordance_lettres_chiffres_sur_le_rendu(self):
        self.assertEqual(
            lettre.controler_montants_rendus(self.html, self.donnees), ())


class TestGabarit(unittest.TestCase):

    def test_aucun_chiffre_litteral_dans_le_gabarit(self):
        source = (GABARITS / 'ao' / 'lettre_soumission.html').read_text(
            encoding='utf-8')
        self.assertEqual(litteraux_chiffres(source), ())

    def test_validite_par_defaut_quand_la_consultation_ne_l_impose_pas(self):
        lignes = bordereau_depose()
        dossier = contexte_dossier(lignes)
        dossier['marche']['validite_offre_jours'] = None
        donnees = lettre.contexte_gabarit(
            lignes, construire_contexte(dossier))
        self.assertEqual(donnees['validite_jours'],
                         lettre.VALIDITE_DEFAUT_JOURS)

    def test_sans_delai_la_lettre_n_en_invente_pas(self):
        lignes = bordereau_depose()
        dossier = contexte_dossier(lignes)
        dossier['marche']['delai_execution_jours'] = None
        donnees = lettre.contexte_gabarit(lignes,
                                          construire_contexte(dossier))
        self.assertEqual(donnees['delai_lettres'], '')
        self.assertNotIn("Délai d'exécution",
                         rendre_gabarit(lettre.NOM_GABARIT, donnees))


class TestDureeEnLettres(unittest.TestCase):

    def test_pluriel_et_singulier(self):
        self.assertEqual(duree_en_lettres(75), 'Soixante-quinze jours')
        self.assertEqual(duree_en_lettres(1), 'Un jour')
        self.assertEqual(duree_en_lettres(None), '')

    def test_majuscules(self):
        self.assertEqual(duree_en_lettres(75, majuscules=True),
                         'SOIXANTE-QUINZE JOURS')

    def test_autre_unite(self):
        self.assertEqual(duree_en_lettres(3, unite='mois', unite_singulier='mois'),
                         'Trois mois')


class TestEtancheite(unittest.TestCase):
    """AOF129 étendu à la lettre — dans le même commit, comme exigé."""

    def test_la_lettre_est_dans_la_liste_du_ratchet(self):
        from apps.ao.tests.test_aof_etancheite_pack import ARTEFACTS_COUVERTS
        libelles = [libelle for libelle, _ in ARTEFACTS_COUVERTS]
        self.assertTrue(any('lettre de soumission' in libelle
                            for libelle in libelles), libelles)

    def test_la_lettre_ne_fuit_aucun_cout(self):
        from apps.ao.tests.test_aof_etancheite_pack import scanner
        self.assertEqual(scanner(rendu()[0]), ())


if __name__ == '__main__':
    unittest.main()
