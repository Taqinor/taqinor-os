"""AOF158 — cascade de prix inverse : le cas réel, au centime.

    python -m unittest apps.ao.tests.test_aof_cascade_solveur -v
"""
import unittest
from decimal import Decimal

from apps.ao.fabrique import cascade
from apps.ao.fabrique import cascade_controles as controles
from apps.ao.fabrique.ordonnancement import total_ht, total_ttc
from apps.ao.tests.aof_fixtures import (TOTAL_HT, TOTAL_TTC,
                                        bordereau_depose)

#: Le coût de revient réel du dossier (AOF157) et le bénéfice net visé.
COUTS_FRDISI = (
    {'poste': 'panneaux', 'montant': Decimal('880000')},
    {'poste': 'structure', 'montant': Decimal('495000')},
    {'poste': 'garantie onduleurs', 'montant': Decimal('30000')},
    {'poste': 'câble solaire', 'montant': Decimal('1051600')},
    {'poste': 'câble 16 mm²', 'montant': Decimal('5000')},
    {'poste': 'main-d\'œuvre', 'montant': Decimal('140000')},
    {'poste': 'aléas', 'montant': Decimal('65000')},
)
COUTS_TOTAL = Decimal('2666600')
BENEFICE_VISE = Decimal('1500000')


class TestCible(unittest.TestCase):
    """2 666 600 + 1 500 000 → 4 166 600 HT / 4 999 920 TTC."""

    def test_le_total_des_couts(self):
        self.assertEqual(
            sum(poste['montant'] for poste in COUTS_FRDISI), COUTS_TOTAL)

    def test_la_cible_du_dossier_reel(self):
        ht, ttc = cascade.cible(COUTS_FRDISI, BENEFICE_VISE)
        self.assertEqual(ht, TOTAL_HT)
        self.assertEqual(ht, Decimal('4166600'))
        self.assertEqual(ttc, TOTAL_TTC)
        self.assertEqual(ttc, Decimal('4999920'))

    def test_la_cible_reste_sous_le_seuil_des_5_millions(self):
        _, ttc = cascade.cible(COUTS_FRDISI, BENEFICE_VISE)
        self.assertLess(ttc, cascade.SEUIL_PSYCHOLOGIQUE_TTC)

    def test_les_couts_acceptes_en_total_ou_en_postes(self):
        self.assertEqual(cascade.cible(COUTS_TOTAL, BENEFICE_VISE),
                         cascade.cible(COUTS_FRDISI, BENEFICE_VISE))
        self.assertEqual(
            cascade.cible({'a': '2666600'}, BENEFICE_VISE)[0], TOTAL_HT)

    def test_la_marge_est_de_36_pourcent(self):
        resultat = cascade.resoudre(bordereau_depose(), couts=COUTS_FRDISI,
                                    benefice_vise=BENEFICE_VISE)
        self.assertEqual(resultat.marge_pct, Decimal('36.0'))


class TestPasMetier(unittest.TestCase):
    """Les quatre pas sont CALÉS sur les prix réels du bordereau déposé."""

    def test_les_prix_reels_tombent_tous_sur_leur_pas(self):
        for prix in ('2950', '2600', '4500', '8500', '15000', '39500',
                     '50000', '70000', '78000', '120000', '200000',
                     '262000'):
            self.assertTrue(cascade.est_sur_le_pas(Decimal(prix)), prix)

    def test_les_pas_par_ordre_de_grandeur(self):
        self.assertEqual(cascade.pas_de(Decimal('2950')), Decimal('50'))
        self.assertEqual(cascade.pas_de(Decimal('8500')), Decimal('100'))
        self.assertEqual(cascade.pas_de(Decimal('39500')), Decimal('500'))
        self.assertEqual(cascade.pas_de(Decimal('262000')), Decimal('1000'))

    def test_l_arrondi_metier(self):
        self.assertEqual(cascade.arrondir_metier(Decimal('2947.33')),
                         Decimal('2950'))
        self.assertEqual(cascade.arrondir_metier(Decimal('77812.50')),
                         Decimal('78000'))
        self.assertEqual(cascade.arrondir_metier(Decimal('39480')),
                         Decimal('39500'))

    def test_un_prix_a_deux_decimales_n_est_pas_credible(self):
        self.assertFalse(cascade.est_sur_le_pas(Decimal('2947.33')))


#: Les PU de la bibliothèque AVANT ce dossier : la structure de prix est
#: DIFFÉRENTE (modules moins chers, onduleurs plus chers), pas simplement
#: proportionnelle. Une référence homothétique se ferait annuler par le
#: facteur et ne testerait rien.
ANCIENS_PRIX = {
    'mod-a': '2800', 'mod-b': '2800', 'mod-c': '2800',
    'ond-a': '82000', 'ond-b': '82000', 'ond-c': '82000',
    'meteo': '45000', 'afficheur': '42000', 'ems': '180000',
    'genie-civil': '135000',
}


def bordereau_aux_anciens_prix():
    """Le même bordereau, chiffré aux prix de la campagne précédente."""
    return [dict(ligne,
                 prix_unitaire=Decimal(ANCIENS_PRIX.get(
                     ligne['cle'], str(ligne['prix_unitaire']))))
            for ligne in bordereau_depose()]


class TestInvariant(unittest.TestCase):
    """`Σ q × PU == cible` AU CENTIME — asserté, pas espéré."""

    def reference(self):
        return bordereau_aux_anciens_prix()

    def test_la_cascade_atteint_la_cible_au_centime(self):
        lignes = self.reference()
        self.assertNotEqual(total_ht(lignes), TOTAL_HT)
        resultat = cascade.resoudre(lignes, couts=COUTS_FRDISI,
                                    benefice_vise=BENEFICE_VISE)
        self.assertEqual(resultat.total_calcule_ht, TOTAL_HT)
        self.assertEqual(total_ht(resultat.lignes), TOTAL_HT)
        self.assertEqual(total_ttc(resultat.lignes), TOTAL_TTC)

    def test_l_invariant_est_verifiable_de_l_exterieur(self):
        resultat = cascade.resoudre(self.reference(), couts=COUTS_FRDISI,
                                    benefice_vise=BENEFICE_VISE)
        self.assertTrue(cascade.verifier_invariant(resultat.lignes,
                                                   TOTAL_HT))

    def test_l_invariant_mord(self):
        with self.assertRaises(cascade.InvariantRompu):
            cascade.verifier_invariant(bordereau_depose(),
                                       Decimal('4166600.01'))

    def test_le_bordereau_deja_a_la_cible_ne_bouge_pas(self):
        resultat = cascade.resoudre(bordereau_depose(), couts=COUTS_FRDISI,
                                    benefice_vise=BENEFICE_VISE)
        self.assertEqual(resultat.facteur, Decimal('1'))
        self.assertEqual(resultat.residu_reporte, Decimal('0'))
        self.assertEqual(resultat.total_calcule_ht, TOTAL_HT)

    def test_la_cascade_est_idempotente(self):
        """Rejouer la cascade sur son propre résultat ne déplace aucun prix.

        `residu_reporte` n'est PAS nul au second passage : il mesure l'écart
        entre le PU arrondi de la ligne d'ajustement et le PU exact qu'elle
        doit porter. Ce même écart est recalculé à l'identique, donc le prix
        final ne bouge pas — c'est cela, l'idempotence.
        """
        premier = cascade.resoudre(self.reference(), couts=COUTS_FRDISI,
                                   benefice_vise=BENEFICE_VISE)
        second = cascade.resoudre(premier.lignes, couts=COUTS_FRDISI,
                                  benefice_vise=BENEFICE_VISE)
        self.assertEqual([ligne['prix_unitaire'] for ligne in second.lignes],
                         [ligne['prix_unitaire'] for ligne in premier.lignes])
        self.assertEqual(second.total_calcule_ht, TOTAL_HT)


class TestPrixCredibles(unittest.TestCase):

    def setUp(self):
        self.resultat = cascade.resoudre(bordereau_aux_anciens_prix(),
                                         couts=COUTS_FRDISI,
                                         benefice_vise=BENEFICE_VISE)

    def test_tous_les_prix_sauf_l_ajustement_sont_ronds(self):
        hors_pas = cascade.prix_non_ronds(self.resultat)
        self.assertEqual(len(hors_pas), 1)
        self.assertTrue(hors_pas[0]['ligne_ajustement'])
        self.assertEqual(hors_pas[0]['cle'], self.resultat.ligne_ajustement)

    def test_les_prix_repartis_sont_credibles(self):
        """Aucun 2 947,33 : des prix ronds qu'on peut défendre en commission."""
        prix = {ligne['cle']: ligne['prix_unitaire']
                for ligne in self.resultat.lignes}
        self.assertEqual(prix['mod-a'], Decimal('2850'))
        self.assertEqual(prix['ond-a'], Decimal('83000'))
        self.assertEqual(prix['cof-ac-a'], Decimal('8600'))

    def test_la_ligne_d_ajustement_est_un_forfait(self):
        ligne = [ligne for ligne in self.resultat.lignes
                 if ligne['cle'] == self.resultat.ligne_ajustement][0]
        self.assertEqual(ligne['quantite'], Decimal('1'))

    def test_le_residu_est_reporte_et_chiffre(self):
        self.assertEqual(self.resultat.residu_reporte, Decimal('4150.00'))
        self.assertEqual(self.resultat.ligne_ajustement, 'etudes')

    def test_une_ligne_d_ajustement_peut_etre_designee(self):
        resultat = cascade.resoudre(
            bordereau_depose(), couts=COUTS_FRDISI,
            benefice_vise=BENEFICE_VISE, ligne_ajustement='genie-civil')
        self.assertEqual(resultat.ligne_ajustement, 'genie-civil')

    def test_une_ligne_d_ajustement_inconnue_est_refusee(self):
        with self.assertRaises(cascade.AjustementImpossible):
            cascade.resoudre(bordereau_depose(), couts=COUTS_FRDISI,
                             benefice_vise=BENEFICE_VISE,
                             ligne_ajustement='inexistante')

    def test_sans_forfait_la_cascade_refuse_plutot_que_de_rater_la_cible(self):
        lignes = [dict(ligne, quantite=Decimal('3'))
                  for ligne in bordereau_depose()]
        with self.assertRaises(cascade.AjustementImpossible):
            cascade.resoudre(lignes, couts=COUTS_FRDISI,
                             benefice_vise=BENEFICE_VISE)

    def test_un_bordereau_sans_prix_est_refuse(self):
        lignes = [dict(ligne, prix_unitaire=None)
                  for ligne in bordereau_depose()]
        with self.assertRaises(cascade.CascadeImpossible):
            cascade.resoudre(lignes, couts=COUTS_FRDISI,
                             benefice_vise=BENEFICE_VISE)

    def test_un_bordereau_vide_est_refuse(self):
        with self.assertRaises(cascade.CascadeImpossible):
            cascade.resoudre([], couts=COUTS_FRDISI,
                             benefice_vise=BENEFICE_VISE)


class TestAucuneEcritureDeCout(unittest.TestCase):

    def setUp(self):
        self.resultat = cascade.resoudre(bordereau_depose(),
                                         couts=COUTS_FRDISI,
                                         benefice_vise=BENEFICE_VISE)

    def test_la_vue_commune_ne_porte_aucun_cout(self):
        from apps.ao.tests.test_aof_etancheite_pack import scanner
        self.assertEqual(scanner(self.resultat.vers_dict()), ())

    def test_les_lignes_produites_ne_portent_aucun_cout(self):
        from apps.ao.tests.test_aof_etancheite_pack import scanner
        self.assertEqual(scanner(list(self.resultat.lignes)), ())

    def test_la_vue_directeur_est_la_seule_a_porter_l_economie(self):
        vue = self.resultat.vers_dict_directeur()
        self.assertEqual(vue['couts_ht'], str(COUTS_TOTAL))
        self.assertEqual(vue['benefice_vise'], str(BENEFICE_VISE))
        self.assertEqual(vue['marge_pct'], '36.0')

    def test_appliquer_ne_pose_que_des_prix(self):
        lignes = cascade.appliquer(bordereau_depose(), self.resultat)
        for ligne in lignes:
            for cle in ligne:
                self.assertNotIn('cout', str(cle).lower())
                self.assertNotIn('marge', str(cle).lower())


class TestSeuilPsychologique(unittest.TestCase):

    def test_sous_le_seuil_aucune_alerte(self):
        resultat = cascade.resoudre(bordereau_depose(), couts=COUTS_FRDISI,
                                    benefice_vise=BENEFICE_VISE)
        self.assertEqual(resultat.alertes, ())

    def test_au_dessus_du_seuil_une_alerte(self):
        resultat = cascade.resoudre(bordereau_depose(), couts=COUTS_FRDISI,
                                    benefice_vise=Decimal('1700000'))
        self.assertTrue(resultat.alertes)
        self.assertIn('seuil psychologique', resultat.alertes[0])


class TestGardeFouCredibilite(unittest.TestCase):

    def historique(self):
        return [
            {'reference': 'MOD-625', 'famille': 'modules', 'unite': 'U',
             'prix_unitaire': '2900', 'date': '2026-03-04',
             'dossier': 'DV-202603-0011'},
            {'reference': 'MOD-625', 'famille': 'modules', 'unite': 'U',
             'prix_unitaire': '2950', 'date': '2026-07-27',
             'dossier': 'AO-202607-0002'},
            {'reference': 'MOD-625', 'famille': 'modules', 'unite': 'U',
             'prix_unitaire': '3000', 'date': '2026-06-01',
             'dossier': 'AO-202606-0001'},
        ]

    def cascade_avec_familles(self, facteur=Decimal('1')):
        lignes = []
        for ligne in bordereau_depose():
            nouvelle = dict(ligne)
            if ligne['cle'].startswith('mod-'):
                nouvelle['famille'] = 'modules'
                nouvelle['prix_unitaire'] = (ligne['prix_unitaire']
                                             * facteur)
            lignes.append(nouvelle)
        return cascade.resoudre(lignes, couts=COUTS_FRDISI,
                                benefice_vise=BENEFICE_VISE)

    def test_un_bordereau_credible_est_publiable(self):
        rapport = controles.controler(self.cascade_avec_familles(),
                                      self.historique())
        self.assertTrue(rapport.publiable)
        self.assertEqual(rapport.alertes, ())

    def test_un_prix_hors_bande_est_signale_avec_sa_source(self):
        rapport = controles.controler(self.cascade_avec_familles(
            facteur=Decimal('2')), self.historique())
        alertes = [c for c in rapport.alertes if c.code == 'prix_hors_bande']
        self.assertTrue(alertes)
        self.assertIn('observation', alertes[0].motif)
        self.assertIn('modules', alertes[0].motif)

    def test_le_rapport_est_trie_par_impact(self):
        rapport = controles.controler(self.cascade_avec_familles(
            facteur=Decimal('2')), self.historique())
        impacts = [c.impact for c in rapport.alertes]
        self.assertEqual(impacts, sorted(impacts, reverse=True))

    def test_le_refus_est_optionnel(self):
        rapport = controles.controler(
            self.cascade_avec_familles(facteur=Decimal('2')),
            self.historique(), refuser_hors_bande=True)
        self.assertFalse(rapport.publiable)
        with self.assertRaises(AssertionError):
            controles.exiger_publiable(rapport)

    def test_une_famille_sans_historique_est_annoncee(self):
        rapport = controles.controler(self.cascade_avec_familles(), [])
        codes = {c.code for c in rapport.controles}
        self.assertIn('famille_sans_historique', codes)

    def test_le_residu_sur_la_ligne_d_ajustement_reste_en_info(self):
        resultat = cascade.resoudre(bordereau_aux_anciens_prix(),
                                    couts=COUTS_FRDISI,
                                    benefice_vise=BENEFICE_VISE)
        rapport = controles.controler(resultat, self.historique())
        residus = [c for c in rapport.controles
                   if c.code == 'residu_sur_ligne_ajustement']
        self.assertEqual(len(residus), 1)
        self.assertEqual(residus[0].niveau, controles.NIVEAU_INFO)
        self.assertTrue(rapport.publiable)

    def test_un_invariant_rompu_apres_coup_est_un_refus(self):
        resultat = cascade.resoudre(bordereau_depose(), couts=COUTS_FRDISI,
                                    benefice_vise=BENEFICE_VISE)
        retouchee = cascade.Cascade(
            cible_ht=resultat.cible_ht, cible_ttc=resultat.cible_ttc,
            taux_tva=resultat.taux_tva, facteur=resultat.facteur,
            lignes=tuple([dict(resultat.lignes[0],
                               prix_unitaire=Decimal('1'))]
                         + list(resultat.lignes[1:])),
            ligne_ajustement=resultat.ligne_ajustement)
        rapport = controles.controler(retouchee, self.historique())
        self.assertFalse(rapport.publiable)
        self.assertEqual(rapport.refus[0].code, 'invariant_rompu')

    def test_serialisation_du_rapport(self):
        d = controles.controler(self.cascade_avec_familles(),
                                self.historique()).vers_dict()
        self.assertIs(d['publiable'], True)
        self.assertIsInstance(d['controles'], list)


if __name__ == '__main__':
    unittest.main()
