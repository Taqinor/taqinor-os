"""AOF125 — montants en lettres par ligne, arrêté, concordance lettres/chiffres.

    python -m unittest apps.ao.tests.test_aof_montants -v
"""
import unittest
from decimal import Decimal

from apps.ao.fabrique import montants as mnt
from apps.ao.fabrique import ordonnancement as ord_
from apps.ao.tests.aof_fixtures import (ARRETE_TTC, TOTAL_HT, TOTAL_TTC,
                                        bordereau_depose)


class TestArrete(unittest.TestCase):

    def test_l_arrete_officiel_du_dossier(self):
        self.assertEqual(mnt.en_lettres(TOTAL_TTC), ARRETE_TTC)

    def test_la_phrase_d_arrete_est_generee(self):
        phrase = mnt.arrete(TOTAL_TTC)
        self.assertIn(ARRETE_TTC, phrase)
        self.assertTrue(phrase.startswith('Arrêté le présent bordereau'))
        self.assertIn('toutes taxes comprises', phrase)

    def test_prefixe_personnalisable(self):
        self.assertTrue(mnt.arrete(TOTAL_TTC, prefixe='Arrêté la présente '
                                                      'offre').startswith(
            'Arrêté la présente offre :'))

    def test_total_ht_en_lettres(self):
        self.assertEqual(
            mnt.en_lettres(TOTAL_HT),
            'QUATRE MILLIONS CENT SOIXANTE-SIX MILLE SIX CENTS DIRHAMS')

    def test_montant_absent_ne_produit_rien(self):
        self.assertEqual(mnt.en_lettres(None), '')
        self.assertEqual(mnt.arrete(None), '')


class TestLignesEnLettres(unittest.TestCase):

    def setUp(self):
        self.vues = mnt.lignes_en_lettres(bordereau_depose())

    def test_chaque_ligne_porte_son_pu_en_lettres(self):
        for vue in self.vues:
            self.assertTrue(vue.prix_unitaire_lettres, vue.designation)
            self.assertIn('DIRHAM', vue.prix_unitaire_lettres)

    def test_le_pu_des_modules_en_lettres(self):
        modules = [v for v in self.vues if v.cle == 'mod-a'][0]
        self.assertEqual(modules.prix_unitaire, Decimal('2950'))
        self.assertEqual(modules.prix_unitaire_lettres,
                         'DEUX MILLE NEUF CENT CINQUANTE DIRHAMS')
        self.assertIn('2', modules.prix_unitaire_chiffres)

    def test_le_total_de_ligne_est_celui_de_l_ordonnancement(self):
        modules = [v for v in self.vues if v.cle == 'mod-a'][0]
        self.assertEqual(modules.total, Decimal('448400.00'))

    def test_la_vue_ne_modifie_pas_les_lignes(self):
        lignes = bordereau_depose()
        avant = [dict(ligne) for ligne in lignes]
        mnt.lignes_en_lettres(lignes)
        self.assertEqual([dict(ligne) for ligne in lignes], avant)

    def test_les_lettres_sont_recalculees_a_chaque_appel(self):
        premier = mnt.lignes_en_lettres(bordereau_depose())
        second = mnt.lignes_en_lettres(bordereau_depose())
        self.assertEqual([v.prix_unitaire_lettres for v in premier],
                         [v.prix_unitaire_lettres for v in second])

    def test_une_ligne_sans_pu_n_invente_pas_de_lettres(self):
        vues = mnt.lignes_en_lettres([
            {'cle': 'x', 'designation': 'À chiffrer', 'quantite': 1,
             'prix_unitaire': None}])
        self.assertEqual(vues[0].prix_unitaire_lettres, '')
        self.assertIsNone(vues[0].total)


class TestAucunStockage(unittest.TestCase):

    def test_un_champ_de_base_portant_les_lettres_est_refuse(self):
        for champ in mnt.CHAMPS_INTERDITS_EN_BASE:
            with self.assertRaises(mnt.LettresStockees, msg=champ):
                mnt.verifier_absence_de_stockage(['designation', champ])

    def test_un_modele_sain_passe(self):
        self.assertTrue(mnt.verifier_absence_de_stockage(
            ['designation', 'prix_unitaire', 'quantite']))


class TestConcordance(unittest.TestCase):

    def piece(self, total=TOTAL_TTC, lettres=None):
        """Une pièce rendue : chiffres + lettres, comme un vrai document."""
        return ('Le présent bordereau totalise %s.\n%s'
                % (mnt.en_chiffres(total),
                   lettres if lettres is not None else mnt.arrete(total)))

    def test_une_piece_concordante_ne_remonte_rien(self):
        self.assertEqual(
            mnt.controler_concordance(self.piece(), {'total TTC': TOTAL_TTC}),
            ())
        self.assertTrue(
            mnt.exiger_concordance(self.piece(), {'total TTC': TOTAL_TTC}))

    def test_des_lettres_recopiees_d_un_autre_montant_sont_detectees(self):
        """LE défaut réel : le bordereau frère resté à 5 219 280."""
        piece = self.piece(TOTAL_TTC,
                           lettres=mnt.arrete(Decimal('5219280')))
        divergences = mnt.controler_concordance(piece,
                                                {'total TTC': TOTAL_TTC})
        self.assertEqual(len(divergences), 1)
        self.assertFalse(divergences[0].lettres_presentes)
        self.assertTrue(divergences[0].chiffres_presents)
        self.assertIn('PAS les lettres', divergences[0].motif)

    def test_des_chiffres_permutes_sont_detectes(self):
        """5 143 680 tapé pour 5 413 680."""
        piece = ('Total : %s\n%s' % (mnt.en_chiffres(Decimal('5143680')),
                                     mnt.arrete(Decimal('5413680'))))
        divergences = mnt.controler_concordance(
            piece, {'total TTC': Decimal('5413680')})
        self.assertEqual(len(divergences), 1)
        self.assertTrue(divergences[0].lettres_presentes)
        self.assertFalse(divergences[0].chiffres_presents)
        self.assertIn('PAS les chiffres', divergences[0].motif)

    def test_un_montant_absent_de_la_piece_est_detecte(self):
        divergences = mnt.controler_concordance(
            self.piece(), {'total HT': TOTAL_HT})
        self.assertEqual(len(divergences), 1)
        self.assertIn('ni les chiffres ni les lettres', divergences[0].motif)

    def test_le_controle_bloquant_leve(self):
        with self.assertRaises(mnt.ConcordanceRompue):
            mnt.exiger_concordance(self.piece(), {'total HT': TOTAL_HT})

    def test_les_espaces_insecables_ne_font_pas_diverger(self):
        piece = self.piece().replace(' ', ' ').replace(' ', ' ')
        self.assertEqual(
            mnt.controler_concordance(piece, {'total TTC': TOTAL_TTC}), ())

    def test_concordance_ligne_a_ligne_sur_le_bordereau_reel(self):
        lignes = bordereau_depose()
        vues = mnt.lignes_en_lettres(lignes)
        piece = '\n'.join('%s %s %s' % (v.designation,
                                        v.prix_unitaire_chiffres,
                                        v.prix_unitaire_lettres)
                          for v in vues)
        attendus = {('ligne %s' % v.cle): v.prix_unitaire for v in vues}
        self.assertEqual(mnt.controler_concordance(piece, attendus), ())

    def test_serialisation_d_une_divergence(self):
        piece = self.piece(TOTAL_TTC,
                           lettres=mnt.arrete(Decimal('5219280')))
        d = mnt.controler_concordance(piece,
                                      {'total TTC': TOTAL_TTC})[0].vers_dict()
        self.assertEqual(d['repere'], 'total TTC')
        self.assertIn('QUATRE MILLIONS', d['lettres_attendues'])


class TestPublication(unittest.TestCase):

    def test_les_lettres_ne_sont_gelees_qu_a_la_publication(self):
        version = mnt.geler_pour_publication(
            'a' * 64, {'total TTC': TOTAL_TTC, 'total HT': TOTAL_HT})
        self.assertEqual(version.lettre_de('total TTC'), ARRETE_TTC)
        self.assertEqual(version.empreinte_contexte, 'a' * 64)

    def test_la_version_publiee_porte_chiffres_et_lettres(self):
        d = mnt.geler_pour_publication('b' * 64,
                                       {'total TTC': TOTAL_TTC}).vers_dict()
        self.assertIn('total TTC', d['lettres'])
        self.assertIn('total TTC', d['chiffres'])

    def test_une_publication_ne_change_pas_le_dossier(self):
        lignes = bordereau_depose()
        avant = ord_.total_ttc(lignes)
        mnt.geler_pour_publication('c' * 64, {'total TTC': avant})
        self.assertEqual(ord_.total_ttc(lignes), avant)


if __name__ == '__main__':
    unittest.main()
