"""AOF121 — import du cadre acheteur BPU/DQE et verrouillage de sa structure.

    python -m unittest apps.ao.tests.test_aof_import_bordereau -v
"""
import unittest
from decimal import Decimal

from apps.ao.fabrique import import_bordereau as imp

ENTETES = ['N°', 'Désignation des prestations', 'Unité', 'Quantité',
           'Prix unitaire en chiffres', 'Prix total']

CADRE = [
    {'N°': '1', 'Désignation des prestations': 'Modules photovoltaïques',
     'Unité': 'U', 'Quantité': '560', 'Prix unitaire en chiffres': '',
     'Prix total': ''},
    {'N°': '2', 'Désignation des prestations': 'Onduleurs',
     'Unité': 'U', 'Quantité': '3', 'Prix unitaire en chiffres': '',
     'Prix total': ''},
    {'N°': '3', 'Désignation des prestations': 'Batteries de stockage',
     'Unité': 'kWh', 'Quantité': '1 234,50',
     'Prix unitaire en chiffres': '', 'Prix total': ''},
]


class TestMapping(unittest.TestCase):

    def test_detection_automatique(self):
        mapping = imp.detecter_mapping(ENTETES)
        self.assertEqual(mapping['numero'], 'N°')
        self.assertEqual(mapping['designation'],
                         'Désignation des prestations')
        self.assertEqual(mapping['unite'], 'Unité')
        self.assertEqual(mapping['quantite'], 'Quantité')
        self.assertEqual(mapping['prix_unitaire'],
                         'Prix unitaire en chiffres')

    def test_apercu_liste_les_colonnes_ignorees(self):
        vue = imp.apercu(ENTETES, CADRE)
        self.assertIn('Prix total', vue.colonnes_ignorees)

    def test_mapping_manuel_prime(self):
        vue = imp.apercu(ENTETES, CADRE,
                         mapping={'designation': 'Unité',
                                  'quantite': 'Quantité'})
        self.assertEqual(vue.lignes[0].designation, 'U')

    def test_colonne_obligatoire_absente_bloque(self):
        vue = imp.apercu(['Truc'], [{'Truc': 'x'}])
        self.assertFalse(vue.importable)
        with self.assertRaises(imp.MappingIncomplet):
            imp.importer(['Truc'], [{'Truc': 'x'}])


class TestImportSansAlteration(unittest.TestCase):

    def test_le_cadre_est_importe_a_l_identique(self):
        lignes = imp.importer(ENTETES, CADRE)
        self.assertEqual(len(lignes), 3)
        self.assertEqual(lignes[0].designation, 'Modules photovoltaïques')
        self.assertEqual(lignes[0].quantite, Decimal('560'))
        self.assertEqual(lignes[1].unite, 'U')
        self.assertEqual(lignes[2].quantite, Decimal('1234.50'))

    def test_toutes_les_lignes_sont_verrouillees_et_sourcees_acheteur(self):
        for ligne in imp.importer(ENTETES, CADRE):
            self.assertTrue(ligne.verrouillee)
            self.assertEqual(ligne.quantite_source, imp.SOURCE_ACHETEUR)

    def test_modifier_une_quantite_du_cadre_est_refuse(self):
        ligne = imp.importer(ENTETES, CADRE)[0]
        for champ in ('quantite', 'designation', 'unite', 'numero'):
            with self.assertRaises(imp.ChampVerrouille, msg=champ):
                ligne.appliquer(**{champ: 'x'})

    def test_seul_le_pu_et_les_champs_a_nous_sont_editables(self):
        ligne = imp.importer(ENTETES, CADRE)[0]
        modifiee = ligne.appliquer(prix_unitaire=Decimal('2950'),
                                   observation='fiche jointe')
        self.assertEqual(modifiee.quantite, ligne.quantite)
        self.assertEqual(modifiee.designation, ligne.designation)
        self.assertEqual(modifiee.prix_unitaire, Decimal('2950'))

    def test_un_champ_inconnu_est_refuse(self):
        with self.assertRaises(imp.ChampVerrouille):
            imp.importer(ENTETES, CADRE)[0].appliquer(total_ht=Decimal('1'))

    def test_lignes_vides_ignorees(self):
        avec_vide = CADRE + [{'N°': '', 'Désignation des prestations': '',
                              'Unité': '', 'Quantité': ''}]
        self.assertEqual(len(imp.importer(ENTETES, avec_vide)), 3)

    def test_quantite_illisible_signalee_sans_inventer(self):
        cadre = [dict(CADRE[0], **{'Quantité': 'à préciser'})]
        vue = imp.apercu(ENTETES, cadre)
        self.assertIsNone(vue.lignes[0].quantite)
        self.assertTrue(any('illisible' in a for a in vue.anomalies))

    def test_numero_duplique_signale(self):
        cadre = CADRE + [dict(CADRE[0])]
        self.assertTrue(any('déjà présent'
                            in a for a in imp.apercu(ENTETES, cadre).anomalies))


class TestReportDesPrix(unittest.TestCase):

    def test_nos_prix_se_posent_sans_toucher_a_la_structure(self):
        lignes = imp.importer(ENTETES, CADRE)
        avec_prix = imp.reporter_prix(lignes, {'1': '2950', '2': '78000'})
        self.assertEqual(avec_prix[0].prix_unitaire, Decimal('2950'))
        self.assertEqual(avec_prix[0].quantite, Decimal('560'))
        self.assertEqual(avec_prix[0].total, Decimal('1652000'))
        self.assertIsNone(avec_prix[2].prix_unitaire)

    def test_total_de_ligne_indisponible_sans_pu(self):
        self.assertIsNone(imp.importer(ENTETES, CADRE)[0].total)


class TestIdempotence(unittest.TestCase):

    def test_reimporter_le_meme_cadre_ne_change_rien(self):
        premier = imp.reporter_prix(imp.importer(ENTETES, CADRE),
                                    {'1': '2950'})
        second = imp.importer(ENTETES, CADRE)
        fusionnees, journal = imp.fusionner(premier, second)
        self.assertEqual([ligne.vers_dict() for ligne in fusionnees],
                         [ligne.vers_dict() for ligne in premier])
        self.assertEqual(journal['modifications'], ())
        self.assertEqual(journal['ajouts'], ())

    def test_nos_prix_survivent_a_un_reimport(self):
        premier = imp.reporter_prix(imp.importer(ENTETES, CADRE),
                                    {'1': '2950', '2': '78000'})
        fusionnees, _ = imp.fusionner(premier, imp.importer(ENTETES, CADRE))
        self.assertEqual(fusionnees[0].prix_unitaire, Decimal('2950'))
        self.assertEqual(fusionnees[1].prix_unitaire, Decimal('78000'))

    def test_un_rectificatif_est_signale_pas_silencieux(self):
        premier = imp.importer(ENTETES, CADRE)
        rectifie = list(CADRE)
        rectifie[0] = dict(CADRE[0], **{'Quantité': '600'})
        fusionnees, journal = imp.fusionner(
            premier, imp.importer(ENTETES, rectifie))
        self.assertEqual(journal['modifications'], ('1',))
        self.assertEqual(fusionnees[0].quantite, Decimal('600'))

    def test_ligne_disparue_du_cadre_signalee(self):
        premier = imp.importer(ENTETES, CADRE)
        _, journal = imp.fusionner(premier, imp.importer(ENTETES, CADRE[:2]))
        self.assertEqual(journal['retirees'], ('3',))


class TestRapprochement(unittest.TestCase):

    def calepinage(self):
        return [
            {'cle': '1', 'designation': 'Modules', 'quantite': 560},
            {'cle': 'cables-dc-b', 'designation': 'Câbles DC bâtiment B',
             'quantite': 1},
        ]

    def test_les_ecarts_sont_listes_jamais_fusionnes(self):
        cadre = imp.importer(ENTETES, CADRE)
        rapprochement = imp.rapprocher(cadre, self.calepinage())
        self.assertEqual([e['cle'] for e in rapprochement.ecarts_a_arbitrer],
                         ['cables-dc-b'])
        self.assertIn('arbitrer',
                      rapprochement.ecarts_a_arbitrer[0]['motif'])
        self.assertTrue(rapprochement.arbitrage_requis)

    def test_les_lignes_appariees_sont_nommees(self):
        rapprochement = imp.rapprocher(imp.importer(ENTETES, CADRE),
                                       self.calepinage())
        self.assertIn(('1', '1'), rapprochement.appariees)

    def test_les_lignes_du_cadre_non_servies_sont_listees(self):
        rapprochement = imp.rapprocher(imp.importer(ENTETES, CADRE),
                                       self.calepinage())
        self.assertEqual(rapprochement.cadre_non_servi, ('2', '3'))

    def test_un_appariement_arbitre_est_respecte(self):
        rapprochement = imp.rapprocher(
            imp.importer(ENTETES, CADRE), self.calepinage(),
            appariement={'cables-dc-b': '3'})
        self.assertEqual(rapprochement.ecarts_a_arbitrer, ())
        self.assertIn(('cables-dc-b', '3'), rapprochement.appariees)


class TestLectureDesNombres(unittest.TestCase):

    def test_formats_de_nombre_du_terrain(self):
        cas = {'1 234,50': Decimal('1234.50'), '1234.5': Decimal('1234.5'),
               '1,234.50': Decimal('1234.50'), '560': Decimal('560'),
               '': None, None: None, '  12  ': Decimal('12')}
        for brut, attendu in cas.items():
            self.assertEqual(imp._decimal(brut), attendu, repr(brut))

    def test_normalisation_des_entetes(self):
        self.assertEqual(imp.normaliser_entete('Désignation des prestations'),
                         'designation_des_prestations')
        self.assertEqual(imp.normaliser_entete('N°'), 'n')


if __name__ == '__main__':
    unittest.main()
