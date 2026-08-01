"""AOF123 — déplacement de ligne et renumérotation à TOTAL INVARIANT.

    python -m unittest apps.ao.tests.test_aof_bordereau_ordre -v
"""
import unittest
from decimal import Decimal

from apps.ao.fabrique import ordonnancement as ord_
from apps.ao.tests.aof_fixtures import (
    CLE_CABLES_B, SECTION_A, SECTION_B, SECTION_C, SECTION_COMMUNES,
    SOUS_TOTAUX_ATTENDUS, TOTAL_HT, TOTAL_TTC, TVA,
    bordereau_avant_deplacement)


class TestTotaux(unittest.TestCase):

    def test_le_bordereau_reel_totalise_4_166_600_ht(self):
        self.assertEqual(ord_.total_ht(bordereau_avant_deplacement()),
                         TOTAL_HT)

    def test_tva_et_ttc_reels(self):
        lignes = bordereau_avant_deplacement()
        self.assertEqual(ord_.total_tva(lignes), TVA)
        self.assertEqual(ord_.total_ttc(lignes), TOTAL_TTC)

    def test_cascade_publiee(self):
        calcules = ord_.totaux(bordereau_avant_deplacement())
        self.assertEqual(calcules.sous_total_ht, TOTAL_HT)
        self.assertEqual(calcules.remise, Decimal('0'))
        self.assertEqual(calcules.total_ht, TOTAL_HT)
        self.assertEqual(calcules.tva, TVA)
        self.assertEqual(calcules.total_ttc, TOTAL_TTC)

    def test_une_ligne_sans_pu_ne_compte_pas(self):
        lignes = bordereau_avant_deplacement()
        lignes.append({'cle': 'a-chiffrer', 'section': SECTION_COMMUNES,
                       'designation': 'Poste à chiffrer', 'unite': 'ENS',
                       'quantite': Decimal('1'), 'prix_unitaire': None})
        self.assertEqual(ord_.total_ht(lignes), TOTAL_HT)


class TestDeplacementReel(unittest.TestCase):
    """Le cas du dossier : « câbles DC Bâtiment B » remontés en section B."""

    def setUp(self):
        self.avant = ord_.renumeroter(bordereau_avant_deplacement())
        self.apres = ord_.deplacer(self.avant, CLE_CABLES_B, SECTION_B)

    def test_le_total_est_inchange(self):
        self.assertEqual(ord_.total_ht(self.apres),
                         ord_.total_ht(self.avant))
        self.assertEqual(ord_.total_ttc(self.apres), TOTAL_TTC)

    def test_les_sous_totaux_deviennent_ceux_du_bordereau_depose(self):
        self.assertEqual(ord_.sous_totaux(self.apres), SOUS_TOTAUX_ATTENDUS)

    def test_la_ligne_a_change_de_section(self):
        deplacee = [ligne for ligne in self.apres
                    if ligne['cle'] == CLE_CABLES_B][0]
        self.assertEqual(deplacee['section'], SECTION_B)

    def test_la_renumerotation_est_complete_et_contigue(self):
        numeros = [int(ligne['numero']) for ligne in self.apres]
        self.assertEqual(numeros, list(range(1, len(self.apres) + 1)))

    def test_les_sections_gardent_leur_ordre(self):
        self.assertEqual(ord_.ordre_des_sections(self.apres),
                         (SECTION_A, SECTION_B, SECTION_C, SECTION_COMMUNES))

    def test_aucune_ligne_perdue_ni_dupliquee(self):
        self.assertEqual(sorted(ligne['cle'] for ligne in self.apres),
                         sorted(ligne['cle'] for ligne in self.avant))


class TestInvariance(unittest.TestCase):

    def test_renumeroter_est_idempotent(self):
        une = ord_.renumeroter(bordereau_avant_deplacement())
        deux = ord_.renumeroter(une)
        self.assertEqual([ligne['numero'] for ligne in deux],
                         [ligne['numero'] for ligne in une])

    def test_deplacer_puis_revenir_redonne_les_memes_montants(self):
        depart = ord_.renumeroter(bordereau_avant_deplacement())
        aller = ord_.deplacer(depart, CLE_CABLES_B, SECTION_B)
        retour = ord_.deplacer(aller, CLE_CABLES_B, SECTION_COMMUNES)
        self.assertEqual(ord_.total_ttc(retour), ord_.total_ttc(depart))
        self.assertEqual(ord_.sous_totaux(retour), ord_.sous_totaux(depart))

    def test_l_assertion_d_invariance_mord(self):
        """Si un jour la renumérotation touchait un montant, elle lèverait."""
        avant = ord_.renumeroter(bordereau_avant_deplacement())
        apres = [dict(ligne) for ligne in avant]
        apres[0]['prix_unitaire'] = Decimal('2960')
        with self.assertRaises(ord_.TotalAltere):
            ord_._verifier_invariance(avant, apres, 'un test')

    def test_ligne_introuvable(self):
        with self.assertRaises(ord_.LigneIntrouvable):
            ord_.deplacer(bordereau_avant_deplacement(), 'inexistante',
                          SECTION_B)

    def test_position_choisie_dans_la_section(self):
        apres = ord_.deplacer(ord_.renumeroter(bordereau_avant_deplacement()),
                              CLE_CABLES_B, SECTION_B, position=1)
        section_b = [ligne['cle'] for ligne in apres
                     if ligne['section'] == SECTION_B]
        self.assertEqual(section_b[0], CLE_CABLES_B)
        self.assertEqual(ord_.total_ttc(apres), TOTAL_TTC)

    def test_deplacement_vers_une_section_neuve(self):
        apres = ord_.deplacer(ord_.renumeroter(bordereau_avant_deplacement()),
                              CLE_CABLES_B, 'D — Options')
        self.assertEqual(ord_.total_ttc(apres), TOTAL_TTC)
        self.assertIn('D — Options', ord_.ordre_des_sections(apres))


class TestControles(unittest.TestCase):

    def test_un_bordereau_sain_ne_remonte_rien(self):
        lignes = ord_.renumeroter(bordereau_avant_deplacement())
        self.assertEqual(ord_.controler(lignes), ())

    def test_ligne_vide_detectee(self):
        lignes = bordereau_avant_deplacement()
        lignes.append({'cle': 'vide', 'section': SECTION_COMMUNES,
                       'designation': '', 'unite': 'U', 'quantite': None,
                       'prix_unitaire': None})
        codes = {a.code for a in ord_.controler(lignes)}
        self.assertIn('designation_vide', codes)
        self.assertIn('quantite_absente', codes)
        self.assertIn('pu_absent', codes)

    def test_pu_nul_detecte(self):
        lignes = bordereau_avant_deplacement()
        lignes[0] = dict(lignes[0], prix_unitaire=Decimal('0'))
        self.assertIn('pu_nul', {a.code for a in ord_.controler(lignes)})

    def test_unite_incoherente_detectee_sans_bloquer(self):
        lignes = bordereau_avant_deplacement()
        lignes[5] = dict(lignes[5], unite='ENS')  # modules en ENS
        anomalies = ord_.controler(lignes)
        incoherences = [a for a in anomalies if a.code == 'unite_incoherente']
        self.assertEqual(len(incoherences), 1)
        self.assertFalse(incoherences[0].bloquant)
        self.assertEqual(ord_.bloquants(anomalies), ())

    def test_numerotation_a_trous_detectee(self):
        lignes = ord_.renumeroter(bordereau_avant_deplacement())
        troue = [dict(ligne) for ligne in lignes]
        troue[3]['numero'] = '99'
        codes = {a.code for a in ord_.controler(troue)}
        self.assertIn('numerotation_a_trous', codes)

    def test_numero_duplique_detecte(self):
        lignes = ord_.renumeroter(bordereau_avant_deplacement())
        double = [dict(ligne) for ligne in lignes]
        double[3]['numero'] = double[2]['numero']
        self.assertIn('numero_duplique',
                      {a.code for a in ord_.controler(double)})


class TestRegroupement(unittest.TestCase):

    def test_sections_et_lignes(self):
        groupes = ord_.sections_et_lignes(
            ord_.deplacer(ord_.renumeroter(bordereau_avant_deplacement()),
                          CLE_CABLES_B, SECTION_B))
        self.assertEqual([section for section, _ in groupes],
                         [SECTION_A, SECTION_B, SECTION_C, SECTION_COMMUNES])
        self.assertEqual(len(dict(groupes)[SECTION_B]), 3)

    def test_numero_de(self):
        apres = ord_.deplacer(ord_.renumeroter(bordereau_avant_deplacement()),
                              CLE_CABLES_B, SECTION_B)
        self.assertEqual(ord_.numero_de(apres, CLE_CABLES_B), '8')
        self.assertIsNone(ord_.numero_de(apres, 'inexistante'))


if __name__ == '__main__':
    unittest.main()
