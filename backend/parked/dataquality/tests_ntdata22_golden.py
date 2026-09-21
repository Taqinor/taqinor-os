"""NTDATA22 — modèle `GoldenRecord` (fiche consolidée, générique par chaîne).

Couvre :
  * le critère d'acceptation : un golden record consolide DEUX clients sources
    sous UNE clé métier ;
  * l'unicité par (société, entité, clé métier) — la même clé ne peut pas
    produire deux fiches consolidées concurrentes dans une société ;
  * deux sociétés peuvent porter la MÊME clé métier sans se marcher dessus ;
  * une clé métier vide est refusée EN NOMMANT le champ ;
  * « jamais consolidé » (`derniere_consolidation_le` vide) se distingue de
    « consolidé sans attribut ».
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.crm.models import Client
from apps.dataquality.models import GoldenRecord
from authentication.models import Company


class GoldenRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA22 SA',
                                             slug='ntdata22-sa')
        cls.autre = Company.objects.create(nom='NTDATA22 Autre',
                                           slug='ntdata22-autre')

    def test_consolide_deux_clients_sous_une_cle_metier(self):
        """Critère : 2 fiches sources, 1 clé métier, 1 golden record."""
        premier = Client.objects.create(
            company=self.company, nom='Atlas Energie',
            ice='001234567000089', telephone='0600000001')
        second = Client.objects.create(
            company=self.company, nom='ATLAS ENERGIE SARL',
            ice='001234567000089', email='contact@atlas.ma')

        golden = GoldenRecord.objects.create(
            company=self.company,
            entite=GoldenRecord.Entite.CLIENT,
            cle_metier='001234567000089',
            source_ids=[premier.pk, second.pk],
            attributs={'nom': 'ATLAS ENERGIE SARL',
                       'telephone': '0600000001',
                       'email': 'contact@atlas.ma'},
        )

        self.assertEqual(golden.nb_sources, 2)
        self.assertEqual(golden.source_ids, [premier.pk, second.pk])
        # L'identité consolidée porte ce que chaque source apportait.
        self.assertEqual(golden.attributs['telephone'], '0600000001')
        self.assertEqual(golden.attributs['email'], 'contact@atlas.ma')
        # Les sources ne sont JAMAIS mutées par l'existence du golden record.
        premier.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(premier.nom, 'Atlas Energie')
        self.assertEqual(second.nom, 'ATLAS ENERGIE SARL')

    def test_cle_metier_unique_par_societe_et_entite(self):
        GoldenRecord.objects.create(
            company=self.company, entite=GoldenRecord.Entite.CLIENT,
            cle_metier='0600000001')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GoldenRecord.objects.create(
                    company=self.company,
                    entite=GoldenRecord.Entite.CLIENT,
                    cle_metier='0600000001')

    def test_meme_cle_pour_une_autre_entite_ou_societe(self):
        """La même chaîne n'est pas la même clé : entité et société la portent."""
        GoldenRecord.objects.create(
            company=self.company, entite=GoldenRecord.Entite.CLIENT,
            cle_metier='001234567000089')
        # Même société, autre entité : accepté.
        GoldenRecord.objects.create(
            company=self.company, entite=GoldenRecord.Entite.FOURNISSEUR,
            cle_metier='001234567000089')
        # Autre société, même entité : accepté (isolation multi-tenant).
        GoldenRecord.objects.create(
            company=self.autre, entite=GoldenRecord.Entite.CLIENT,
            cle_metier='001234567000089')
        self.assertEqual(GoldenRecord.objects.count(), 3)
        self.assertEqual(
            GoldenRecord.objects.filter(company=self.company).count(), 2)

    def test_cle_metier_vide_refusee_en_nommant_le_champ(self):
        golden = GoldenRecord(company=self.company,
                              entite=GoldenRecord.Entite.PRODUIT,
                              cle_metier='   ')
        with self.assertRaises(ValidationError) as leve:
            golden.clean()
        self.assertIn('cle_metier', leve.exception.message_dict)

    def test_sources_et_attributs_mal_formes_refuses(self):
        golden = GoldenRecord(company=self.company,
                              entite=GoldenRecord.Entite.PRODUIT,
                              cle_metier='REF-1',
                              source_ids='pas-une-liste',
                              attributs=['pas-un-objet'])
        with self.assertRaises(ValidationError) as leve:
            golden.clean()
        self.assertIn('source_ids', leve.exception.message_dict)
        self.assertIn('attributs', leve.exception.message_dict)

    def test_jamais_consolide_se_distingue_de_consolide_vide(self):
        golden = GoldenRecord.objects.create(
            company=self.company, entite=GoldenRecord.Entite.PRODUIT,
            cle_metier='REF-2')
        self.assertIsNone(golden.derniere_consolidation_le)
        self.assertEqual(golden.attributs, {})
        self.assertEqual(golden.nb_sources, 0)

    def test_str_lisible(self):
        golden = GoldenRecord.objects.create(
            company=self.company, entite=GoldenRecord.Entite.FOURNISSEUR,
            cle_metier='001234567000089')
        self.assertIn('Fournisseur', str(golden))
        self.assertIn('001234567000089', str(golden))
