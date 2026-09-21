"""AOF122 — report des quantités et invariant bordereau ↔ planches.

    python -m unittest apps.ao.tests.test_report_quantites -v
"""
import unittest
from decimal import Decimal

from apps.ao.fabrique import report_quantites as rep

HASH_A, HASH_B, HASH_C = 'a' * 64, 'b' * 64, 'c' * 64


def resultats(compte_c=288, hash_c=HASH_C):
    """Le cas RÉEL : 152 + 120 + 288 = 560 modules."""
    return [
        {'batiment': 'A', 'compte_retenu': 152, 'kwc': 95.0,
         'hash_entree': HASH_A, 'version_moteur': '1.0.0'},
        {'batiment': 'B', 'compte_retenu': 120, 'kwc': 75.0,
         'hash_entree': HASH_B, 'version_moteur': '1.0.0'},
        {'batiment': 'C', 'compte_retenu': compte_c, 'kwc': 180.0,
         'hash_entree': hash_c, 'version_moteur': '1.0.0'},
    ]


def lignes():
    return [
        {'numero': '1', 'designation': 'Modules bâtiment A', 'batiment': 'A',
         'quantite': None, 'quantite_source': rep.SOURCE_CALEPINAGE},
        {'numero': '2', 'designation': 'Modules bâtiment B', 'batiment': 'B',
         'quantite': None, 'quantite_source': rep.SOURCE_CALEPINAGE},
        {'numero': '3', 'designation': 'Modules bâtiment C', 'batiment': 'C',
         'quantite': None, 'quantite_source': rep.SOURCE_CALEPINAGE},
        {'numero': '4', 'designation': 'Génie civil', 'batiment': '',
         'quantite': Decimal('1'), 'quantite_source': rep.SOURCE_MANUELLE},
        # Poste imposé par le cadre acheteur : verrouillé, et porté sur une
        # AUTRE grandeur que le comptage de modules (un forfait d'essais).
        {'numero': '5', 'designation': 'Essais et DOE (cadre acheteur)',
         'batiment': 'A', 'quantite': Decimal('1'), 'grandeur': 'forfait',
         'quantite_source': rep.SOURCE_ACHETEUR, 'verrouillee': True},
    ]


class TestReport(unittest.TestCase):

    def test_les_quantites_des_variantes_sont_reportees(self):
        report = rep.reporter(lignes(), resultats())
        quantites = {ligne['numero']: ligne['quantite']
                     for ligne in report.lignes}
        self.assertEqual(quantites['1'], Decimal('152'))
        self.assertEqual(quantites['2'], Decimal('120'))
        self.assertEqual(quantites['3'], Decimal('288'))

    def test_la_ligne_manuelle_reste_intacte(self):
        report = rep.reporter(lignes(), resultats())
        manuelle = [ligne for ligne in report.lignes
                    if ligne['numero'] == '4'][0]
        self.assertEqual(manuelle['quantite'], Decimal('1'))
        self.assertIn('4', report.ignorees)

    def test_la_ligne_acheteur_verrouillee_reste_intacte(self):
        report = rep.reporter(lignes(), resultats())
        acheteur = [ligne for ligne in report.lignes
                    if ligne['numero'] == '5'][0]
        self.assertEqual(acheteur['quantite'], Decimal('1'))
        self.assertIn('5', report.ignorees)

    def test_la_tracabilite_de_la_variante_est_ecrite(self):
        report = rep.reporter(lignes(), resultats())
        premiere = report.lignes[0]
        self.assertEqual(premiere['variante_hash'], HASH_A)
        self.assertEqual(premiere['version_moteur'], '1.0.0')

    def test_report_en_kwc(self):
        lot = [dict(lignes()[0], grandeur=rep.GRANDEUR_KWC)]
        report = rep.reporter(lot, resultats())
        self.assertEqual(report.lignes[0]['quantite'], Decimal('95.0'))

    def test_grandeur_inconnue_refusee(self):
        lot = [dict(lignes()[0], grandeur='surface')]
        with self.assertRaises(rep.LigneNonReportable):
            rep.reporter(lot, resultats())

    def test_batiment_sans_ligne_de_bordereau_signale(self):
        report = rep.reporter(lignes()[:2], resultats())
        self.assertEqual(report.non_servies, ('C',))

    def test_ligne_sur_un_batiment_sans_variante_est_laissee(self):
        lot = [dict(lignes()[0], batiment='Z')]
        report = rep.reporter(lot, resultats())
        self.assertIsNone(report.lignes[0]['quantite'])
        self.assertIn('1', report.ignorees)


class TestIdempotence(unittest.TestCase):

    def test_rejouer_le_report_ne_change_rien(self):
        premier = rep.reporter(lignes(), resultats())
        second = rep.reporter(premier.lignes, resultats())
        self.assertEqual(second.lignes, premier.lignes)
        self.assertEqual(second.reportees, ())
        self.assertEqual(len(second.inchangees), 3)
        self.assertFalse(second.a_change)

    def test_le_premier_report_est_signale_comme_changement(self):
        self.assertTrue(rep.reporter(lignes(), resultats()).a_change)


class TestRafraichissement(unittest.TestCase):

    def test_un_calepinage_rejoue_marque_le_bordereau_a_rafraichir(self):
        pose = rep.reporter(lignes(), resultats()).lignes
        self.assertEqual(rep.a_rafraichir(pose, resultats()), ())
        nouveaux = resultats(compte_c=314, hash_c='d' * 64)
        self.assertEqual(rep.a_rafraichir(pose, nouveaux), ('3',))

    def test_une_meme_quantite_sur_une_autre_variante_est_detectee(self):
        """Même compte, entrée différente : la traçabilité doit le voir."""
        pose = rep.reporter(lignes(), resultats()).lignes
        nouveaux = resultats(compte_c=288, hash_c='e' * 64)
        self.assertEqual(rep.a_rafraichir(pose, nouveaux), ('3',))

    def test_le_rafraichissement_ne_reecrit_rien_de_lui_meme(self):
        pose = rep.reporter(lignes(), resultats()).lignes
        avant = [dict(ligne) for ligne in pose]
        rep.a_rafraichir(pose, resultats(compte_c=314, hash_c='d' * 64))
        self.assertEqual([dict(ligne) for ligne in pose], avant)


class TestInvariantEngagements(unittest.TestCase):

    def pose(self, **remplacements):
        return rep.reporter(lignes(), resultats(**remplacements)).lignes

    def test_le_cas_reel_152_120_288_egale_560(self):
        pose = self.pose()
        par_batiment = rep.quantites_par_batiment(pose)
        self.assertEqual(par_batiment,
                         {'A': Decimal('152'), 'B': Decimal('120'),
                          'C': Decimal('288')})
        self.assertEqual(rep.total_engage(pose), Decimal('560'))

    def test_invariant_tenu(self):
        self.assertEqual(
            rep.controler_invariant(self.pose(),
                                    {'A': 152, 'B': 120, 'C': 288}), ())

    def test_ecart_detecte_et_chiffre(self):
        ecarts = rep.controler_invariant(self.pose(),
                                         {'A': 152, 'B': 120, 'C': 314})
        self.assertEqual(len(ecarts), 1)
        self.assertEqual(ecarts[0].batiment, 'C')
        self.assertEqual(ecarts[0].delta, Decimal('-26'))
        self.assertIn('bordereau', ecarts[0].vers_dict()['motif'])

    def test_planche_sans_ligne_de_bordereau(self):
        ecarts = rep.controler_invariant(
            [], [{'batiment': 'A', 'modules': 152}])
        self.assertEqual(len(ecarts), 1)
        self.assertIn('absente du bordereau', ecarts[0].motif)

    def test_bordereau_sans_planche(self):
        ecarts = rep.controler_invariant(self.pose(), {'A': 152, 'B': 120})
        self.assertEqual([e.batiment for e in ecarts], ['C'])
        self.assertIn('sans planche', ecarts[0].motif)

    def test_engagements_acceptes_en_liste_ou_en_mapping(self):
        liste = [{'batiment': 'A', 'modules': 152},
                 {'batiment': 'B', 'modules': 120},
                 {'batiment': 'C', 'modules': 288}]
        self.assertEqual(rep.controler_invariant(self.pose(), liste), ())


if __name__ == '__main__':
    unittest.main()
