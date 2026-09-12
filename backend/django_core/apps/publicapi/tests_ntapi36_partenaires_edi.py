"""NTAPI36 — registre de partenaires EDI (identifiants + mappings SKU).

Critère d'acceptation, dans les deux sens :
  * un export vers un partenaire REMPLACE les SKU internes par les codes du
    partenaire ;
  * absence de mapping = SKU BRUT + avertissement (jamais un refus d'export —
    une facture complète ne doit pas être bloquée par un article accessoire
    non mappé).

Le générateur INVOIC qui consomme cette traduction est NTAPI33 (non construit
dans cette lane) : on verrouille donc la TRADUCTION elle-même, qui est la
substance de NTAPI36 et ce que NTAPI33/34/35 appelleront tel quel.
"""
from django.db.utils import IntegrityError
from django.test import TestCase

from authentication.models import Company

from . import edi_partners
from .models import PartenaireEdi


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


class Ntapi36TraductionSortieTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi36', 'NTAPI36')
        self.partenaire = PartenaireEdi.objects.create(
            company=self.co, nom='Centrale Achats SA',
            type_identifiant=PartenaireEdi.TYPE_GLN,
            identifiant='3012345678901',
            format=PartenaireEdi.FORMAT_EDIFACT,
            mapping_sku={'PV-550W': 'CA-9001', 'ONDL-5K': 'CA-9002'})

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_les_sku_sont_remplaces_par_les_codes_partenaire(self):
        lignes, avertissements = edi_partners.traduire_lignes(
            self.partenaire,
            [{'sku': 'PV-550W', 'quantite': 10},
             {'sku': 'ONDL-5K', 'quantite': 1}])
        self.assertEqual([ligne['code_article'] for ligne in lignes],
                         ['CA-9001', 'CA-9002'])
        self.assertTrue(all(ligne['code_mappe'] for ligne in lignes))
        self.assertEqual(avertissements, [])

    def test_sku_non_mappe_part_brut_avec_un_avertissement(self):
        lignes, avertissements = edi_partners.traduire_lignes(
            self.partenaire,
            [{'sku': 'PV-550W'}, {'sku': 'CABLE-6MM'}])
        self.assertEqual(lignes[0]['code_article'], 'CA-9001')
        # SKU BRUT, jamais un refus : la facture complète part quand même.
        self.assertEqual(lignes[1]['code_article'], 'CABLE-6MM')
        self.assertFalse(lignes[1]['code_mappe'])
        self.assertEqual(len(avertissements), 1)
        self.assertIn('CABLE-6MM', avertissements[0])

    def test_sans_partenaire_tout_part_brut_avec_avertissements(self):
        lignes, avertissements = edi_partners.traduire_lignes(
            None, [{'sku': 'PV-550W'}])
        self.assertEqual(lignes[0]['code_article'], 'PV-550W')
        self.assertEqual(len(avertissements), 1)

    def test_les_lignes_source_ne_sont_jamais_mutees(self):
        source = [{'sku': 'PV-550W', 'quantite': 3}]
        edi_partners.traduire_lignes(self.partenaire, source)
        self.assertEqual(source, [{'sku': 'PV-550W', 'quantite': 3}])

    def test_autres_champs_de_ligne_preserves(self):
        lignes, _ = edi_partners.traduire_lignes(
            self.partenaire,
            [{'sku': 'PV-550W', 'quantite': 10, 'prix_unitaire': '1200.00'}])
        self.assertEqual(lignes[0]['quantite'], 10)
        self.assertEqual(lignes[0]['prix_unitaire'], '1200.00')

    def test_lignes_vides(self):
        self.assertEqual(edi_partners.traduire_lignes(self.partenaire, []),
                         ([], []))


class Ntapi36TraductionEntreeTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi36-in', 'NTAPI36 entrée')
        self.partenaire = PartenaireEdi.objects.create(
            company=self.co, nom='Donneur d\'ordre',
            identifiant='987654321',
            type_identifiant=PartenaireEdi.TYPE_DUNS,
            format=PartenaireEdi.FORMAT_X12,
            mapping_sku={'PV-550W': 'DO-77'})

    def test_code_partenaire_resolu_en_sku_interne(self):
        sku, avertissement = edi_partners.resoudre_sku(self.partenaire, 'DO-77')
        self.assertEqual(sku, 'PV-550W')
        self.assertIsNone(avertissement)

    def test_code_inconnu_renvoie_le_code_recu_plus_un_avertissement(self):
        sku, avertissement = edi_partners.resoudre_sku(
            self.partenaire, 'DO-INCONNU')
        self.assertEqual(sku, 'DO-INCONNU')
        self.assertIn('DO-INCONNU', avertissement)


class Ntapi36RegistreTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi36-reg', 'NTAPI36 registre')
        self.autre = _company('ntapi36-autre', 'NTAPI36 autre')

    def test_resolution_par_identifiant_scopee_societe(self):
        PartenaireEdi.objects.create(
            company=self.co, nom='A', identifiant='3001', mapping_sku={})
        self.assertIsNotNone(edi_partners.partenaire_pour(self.co, '3001'))
        # Le mapping d'autrui n'est jamais atteignable depuis une autre société.
        self.assertIsNone(edi_partners.partenaire_pour(self.autre, '3001'))

    def test_partenaire_inactif_non_resolu(self):
        PartenaireEdi.objects.create(
            company=self.co, nom='A', identifiant='3002', actif=False)
        self.assertIsNone(edi_partners.partenaire_pour(self.co, '3002'))

    def test_meme_identifiant_possible_dans_deux_societes(self):
        PartenaireEdi.objects.create(
            company=self.co, nom='A', identifiant='3003')
        PartenaireEdi.objects.create(
            company=self.autre, nom='A', identifiant='3003')
        self.assertEqual(
            PartenaireEdi.objects.filter(identifiant='3003').count(), 2)

    def test_identifiant_unique_par_societe(self):
        PartenaireEdi.objects.create(
            company=self.co, nom='A', identifiant='3004')
        with self.assertRaises(IntegrityError):
            PartenaireEdi.objects.create(
                company=self.co, nom='B', identifiant='3004')

    def test_mapping_illisible_ne_leve_jamais(self):
        partenaire = PartenaireEdi.objects.create(
            company=self.co, nom='A', identifiant='3005',
            mapping_sku=['pas', 'un', 'dict'])
        self.assertIsNone(partenaire.code_pour_sku('PV-550W'))
        lignes, avertissements = edi_partners.traduire_lignes(
            partenaire, [{'sku': 'PV-550W'}])
        self.assertEqual(lignes[0]['code_article'], 'PV-550W')
        self.assertEqual(len(avertissements), 1)
