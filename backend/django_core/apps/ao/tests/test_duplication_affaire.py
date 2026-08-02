"""AOF130 — une affaire dupliquée n'hérite d'aucun résultat.

    python -m unittest apps.ao.tests.test_duplication_affaire -v
"""
import unittest
from decimal import Decimal

from apps.ao.fabrique import duplication as dup
from apps.ao.tests.aof_fixtures import bordereau_depose


def affaire_source():
    lignes = [dict(ligne) for ligne in bordereau_depose()]
    lignes[0]['quantite_source'] = 'calepinage'
    lignes[0]['variante_hash'] = 'a' * 64
    lignes.append({'cle': 'cadre-1', 'section': 'Cadre acheteur',
                   'designation': 'Poste imposé', 'unite': 'ENS',
                   'quantite': Decimal('1'), 'prix_unitaire': Decimal('1000'),
                   'quantite_source': 'acheteur', 'verrouillee': True})
    return {
        'id': 42, 'reference': 'AO-202607-0002', 'statut': 'depose',
        'objet': 'Centrale photovoltaïque en toiture',
        'geometrie': {'batiments': [{'code': 'A', 'contour': [[0, 0], [10, 0]]}]},
        'obstacles': [{'code': 'edicule', 'x': 3.0, 'y': 4.0}],
        'bordereau': lignes,
        'gabarit_pack': {'pieces': ['00-checklist', '04-bordereau']},
        'exigences': [{'code': 'assurance', 'libelle': 'RC décennale'}],
        'pieces_jointes': [{'id': 7, 'reference': 'att-7',
                            'libelle': 'DCE complet'}],
        # Tout ce qui suit ne doit JAMAIS survivre.
        'variantes': [{'batiment': 'A', 'compte_retenu': 152}],
        'calepinage': [{'batiment': 'A', 'compte_retenu': 152}],
        'engagements': [{'batiment': 'A', 'modules': 152}],
        'economie': {'benefice_net_ht': 1500000},
        'lignes_cout_revient': [{'poste': 'modules', 'montant': 1176000}],
        'pieces_generees': [{'code': 'bordereau', 'fichier': 'x.pdf'}],
        'artefacts': [{'code': 'lettre', 'empreinte': 'b' * 64}],
        'depot': {'date': '2026-08-20'}, 'caution': {'montant': 50000},
        'resultat': {'gagne': False}, 'ecart_prix': Decimal('-4.2'),
        'empreinte': 'c' * 64,
    }


class TestAucunResultatHerite(unittest.TestCase):

    def setUp(self):
        self.source = affaire_source()
        self.nouvelle, self.plan = dup.dupliquer_affaire(self.source)

    def test_aucune_variante_calculee(self):
        for cle in ('variantes', 'calepinage', 'engagements'):
            self.assertNotIn(cle, self.nouvelle, cle)

    def test_aucune_economie_ni_cout_de_revient(self):
        for cle in ('economie', 'lignes_cout_revient'):
            self.assertNotIn(cle, self.nouvelle, cle)

    def test_aucune_piece_generee(self):
        for cle in ('pieces_generees', 'artefacts', 'empreinte'):
            self.assertNotIn(cle, self.nouvelle, cle)

    def test_aucun_element_de_depot_ni_de_resultat(self):
        for cle in ('depot', 'caution', 'resultat', 'ecart_prix'):
            self.assertNotIn(cle, self.nouvelle, cle)

    def test_le_controle_d_absence_est_vert(self):
        self.assertEqual(dup.controler_absence_de_resultats(self.nouvelle), ())

    def test_le_controle_mord_sur_un_resultat_herite(self):
        polluee = dict(self.nouvelle, economie={'benefice_net_ht': 1500000})
        self.assertIn('economie', dup.controler_absence_de_resultats(polluee))

    def test_le_controle_mord_sur_une_quantite_de_calepinage_heritee(self):
        polluee = dict(self.nouvelle)
        polluee['bordereau'] = [dict(polluee['bordereau'][0],
                                     quantite=Decimal('152'))]
        fautes = dup.controler_absence_de_resultats(polluee)
        self.assertTrue(any('quantité de calepinage héritée' in f
                            for f in fautes))


class TestStructureHeritee(unittest.TestCase):

    def setUp(self):
        self.source = affaire_source()
        self.nouvelle, self.plan = dup.dupliquer_affaire(self.source)

    def test_la_geometrie_et_les_obstacles_sont_repris(self):
        self.assertEqual(self.nouvelle['geometrie'], self.source['geometrie'])
        self.assertEqual(self.nouvelle['obstacles'], self.source['obstacles'])

    def test_le_gabarit_de_pack_et_les_exigences_sont_repris(self):
        self.assertEqual(self.nouvelle['gabarit_pack'],
                         self.source['gabarit_pack'])
        self.assertEqual(self.nouvelle['exigences'], self.source['exigences'])

    def test_la_copie_est_profonde(self):
        self.nouvelle['obstacles'][0]['x'] = 99.0
        self.assertEqual(self.source['obstacles'][0]['x'], 3.0)

    def test_la_structure_du_bordereau_est_reprise(self):
        designations = {ligne['designation']
                        for ligne in self.nouvelle['bordereau']}
        self.assertIn('Modules photovoltaïques 625 Wc', designations)
        self.assertIn('Génie civil', designations)

    def test_les_pu_de_reference_survivent(self):
        modules = [ligne for ligne in self.nouvelle['bordereau']
                   if ligne['cle'] == 'mod-a'][0]
        self.assertEqual(modules['prix_unitaire'], Decimal('2950'))
        self.assertIsNone(modules['quantite'])

    def test_les_quantites_manuelles_survivent(self):
        genie = [ligne for ligne in self.nouvelle['bordereau']
                 if ligne['cle'] == 'genie-civil'][0]
        self.assertEqual(genie['quantite'], Decimal('1'))


class TestCadreAcheteur(unittest.TestCase):

    def test_les_lignes_du_cadre_acheteur_ne_sont_pas_copiees(self):
        """Un BPU appartient à SA consultation."""
        nouvelle, plan = dup.dupliquer_affaire(affaire_source())
        cles = {ligne['cle'] for ligne in nouvelle['bordereau']}
        self.assertNotIn('cadre-1', cles)
        self.assertIn('cadre-1', plan.lignes_acheteur_ecartees)

    def test_l_ecart_est_annonce_pas_silencieux(self):
        _, plan = dup.dupliquer_affaire(affaire_source())
        self.assertIn('cadre acheteur', plan.resume)


class TestPiecesJointes(unittest.TestCase):

    def test_les_pieces_sont_referencees_et_non_recopiees(self):
        nouvelle, plan = dup.dupliquer_affaire(affaire_source())
        piece = nouvelle['pieces_jointes'][0]
        self.assertEqual(piece['reference'], 'att-7')
        self.assertIs(piece['copie_stockage'], False)
        self.assertIn('att-7', plan.pieces_jointes_referencees)


class TestOptionsEtIdentite(unittest.TestCase):

    def test_la_reference_est_laissee_a_core_numbering(self):
        nouvelle, _ = dup.dupliquer_affaire(affaire_source())
        self.assertIsNone(nouvelle['reference'])
        self.assertEqual(nouvelle['duplique_de'], 'AO-202607-0002')

    def test_le_statut_repart_a_identifie(self):
        nouvelle, _ = dup.dupliquer_affaire(affaire_source())
        self.assertEqual(nouvelle['statut'], dup.STATUT_INITIAL)

    def test_l_objet_est_derive_ou_fourni(self):
        nouvelle, _ = dup.dupliquer_affaire(affaire_source())
        self.assertIn('(copie)', nouvelle['objet'])
        precise, _ = dup.dupliquer_affaire(affaire_source(),
                                           objet='Lycée Ibn Sina')
        self.assertEqual(precise['objet'], 'Lycée Ibn Sina')

    def test_copie_partielle(self):
        nouvelle, plan = dup.dupliquer_affaire(affaire_source(),
                                               copier=('geometrie',))
        self.assertIn('geometrie', nouvelle)
        self.assertNotIn('bordereau', nouvelle)
        self.assertEqual(plan.copie, ('geometrie',))

    def test_option_inconnue_refusee(self):
        with self.assertRaises(dup.OptionDeCopieInconnue):
            dup.dupliquer_affaire(affaire_source(), copier=('economie',))

    def test_duplication_deterministe(self):
        une, _ = dup.dupliquer_affaire(affaire_source())
        deux, _ = dup.dupliquer_affaire(affaire_source())
        self.assertEqual(une, deux)

    def test_la_source_n_est_pas_modifiee(self):
        source = affaire_source()
        avant = len(source['bordereau'])
        dup.dupliquer_affaire(source)
        self.assertEqual(len(source['bordereau']), avant)
        self.assertEqual(source['statut'], 'depose')


class TestPlanEtTrace(unittest.TestCase):

    def test_le_plan_est_lisible_avant_execution(self):
        plan = dup.plan_de_duplication(affaire_source())
        self.assertEqual(plan.copie, dup.COPIABLES)
        self.assertIn('economie', plan.ecarte)
        self.assertIn('mod-a', plan.quantites_a_recalculer)

    def test_la_trace_de_chatter_est_prete(self):
        source = affaire_source()
        nouvelle, plan = dup.dupliquer_affaire(source)
        trace = dup.trace_chatter(source, nouvelle, plan)
        self.assertEqual(trace['objet'], 'ao.appeloffre')
        self.assertIn('dupliquée', trace['message'])
        self.assertIn('copie', trace['detail'])

    def test_serialisation_du_plan(self):
        d = dup.plan_de_duplication(affaire_source()).vers_dict()
        self.assertEqual(d['lignes_acheteur_ecartees'], ['cadre-1'])


if __name__ == '__main__':
    unittest.main()
