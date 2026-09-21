"""NTMIG14 — transformations de valeurs par kit (normalisation à la volée).

Unitaire, pas de DB nécessaire : ces fonctions ne touchent ni fichier ni base.
"""
from django.test import SimpleTestCase

from apps.migration import transforms


class NormaliserTelephoneMaTests(SimpleTestCase):

    def test_odoo_et_sage_produisent_la_meme_valeur(self):
        """Le cas d'école de la tâche : deux formats source, même résultat."""
        odoo = transforms.normaliser_telephone_ma('+212 6 12 34 56 78')
        sage = transforms.normaliser_telephone_ma('0612345678')
        self.assertEqual(odoo, sage)

    def test_reutilise_normalize_phone_du_crm(self):
        from apps.crm.services import normalize_phone

        valeur = '+212 6 12 34 56 78'
        self.assertEqual(
            transforms.normaliser_telephone_ma(valeur),
            normalize_phone(valeur))

    def test_valeur_vide_inchangee(self):
        self.assertEqual(transforms.normaliser_telephone_ma(''), '')
        self.assertIsNone(transforms.normaliser_telephone_ma(None))


class ParserMontantVirguleTests(SimpleTestCase):

    def test_decimale_virgule(self):
        self.assertEqual(transforms.parser_montant_virgule('1 234,56'), '1234.56')

    def test_decimale_point_deja_correcte(self):
        self.assertEqual(transforms.parser_montant_virgule('1234.56'), '1234.56')

    def test_suffixe_mad_dh_retire(self):
        self.assertEqual(transforms.parser_montant_virgule('1500 MAD'), '1500')
        self.assertEqual(transforms.parser_montant_virgule('1500 DH'), '1500')

    def test_valeur_illisible_renvoyee_telle_quelle(self):
        self.assertEqual(transforms.parser_montant_virgule('n/a'), 'n/a')


class ParserDateMultiFormatTests(SimpleTestCase):

    def test_formats_source_multiples_vers_iso(self):
        self.assertEqual(
            transforms.parser_date_multi_format('2026-07-09'), '2026-07-09')
        self.assertEqual(
            transforms.parser_date_multi_format('09/07/2026'), '2026-07-09')
        self.assertEqual(
            transforms.parser_date_multi_format('09-07-2026'), '2026-07-09')

    def test_date_typee_deja_acceptee(self):
        import datetime
        self.assertEqual(
            transforms.parser_date_multi_format(datetime.date(2026, 7, 9)),
            '2026-07-09')

    def test_format_inconnu_renvoye_tel_quel(self):
        self.assertEqual(
            transforms.parser_date_multi_format('bidon'), 'bidon')


class TrimUpperTests(SimpleTestCase):

    def test_espaces_et_casse(self):
        self.assertEqual(transforms.trim_upper('  Odoo  '), 'ODOO')


class MapperStatutTests(SimpleTestCase):

    def test_mappe_via_table(self):
        table = {'won': 'accepte', 'lost': 'refuse'}
        self.assertEqual(transforms.mapper_statut('WON', table), 'accepte')

    def test_valeur_hors_table_inchangee(self):
        self.assertEqual(
            transforms.mapper_statut('inconnu', {'won': 'accepte'}),
            'inconnu')


class AppliquerLigneTests(SimpleTestCase):
    """Le pipeline complet : mapping colonne→champ + transformations par
    champ, appliqué à UNE ligne source."""

    def test_transformation_appliquee_a_la_bonne_colonne(self):
        mapping = {'phone': 'telephone', 'name': 'nom'}
        transformations = {'telephone': ['normaliser_telephone_ma']}
        row = {'phone': '0612345678', 'name': 'Alpha'}

        resultat = transforms.appliquer_ligne(row, mapping, transformations)

        self.assertEqual(resultat['phone'], '612345678')
        self.assertEqual(resultat['name'], 'Alpha')  # non touché

    def test_sans_transformations_ligne_inchangee(self):
        row = {'phone': '0612345678'}
        resultat = transforms.appliquer_ligne(row, {'phone': 'telephone'}, {})
        self.assertEqual(resultat, row)

    def test_transformation_parametree_mapper_statut(self):
        mapping = {'state': 'statut'}
        transformations = {'statut': [
            {'nom': 'mapper_statut', 'table': {'won': 'accepte'}}]}
        resultat = transforms.appliquer_ligne(
            {'state': 'won'}, mapping, transformations)
        self.assertEqual(resultat['state'], 'accepte')
