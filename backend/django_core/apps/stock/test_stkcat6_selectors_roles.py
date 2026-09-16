"""STKCAT6 — les deux sélecteurs cross-app du rail « catégorie typée ».

Ce que ces tests verrouillent, et qui n'est PAS négociable :

  * un produit GLOBAL (``company`` NULL — le catalogue semé par
    ``seed_catalogue``) est rendu à TOUTE société : c'est la portée exacte du
    catalogue de composition (``Q(company=company) | Q(company__isnull=True)``)
    et c'est pour ça que la pergola semée globalement est visible ;
  * un produit (ou une catégorie) d'une AUTRE société n'est JAMAIS rendu — le
    filtre société est posé DANS le sélecteur, aucun appelant ne peut en
    sortir ;
  * un produit ARCHIVÉ ne remonte pas, et ``avec_prix=True`` (le défaut)
    applique la règle du dépôt : une fiche sans prix de vente réel n'est jamais
    auto-cotée.
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import Categorie, Produit
from apps.stock.selectors import (
    categories_par_type, produits_par_type_equipement)
from authentication.models import Company


class STKCAT6Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='stkcat6-co', defaults={'nom': 'STKCAT6 Co'})[0]
        cls.other_company = Company.objects.get_or_create(
            slug='stkcat6-co-other', defaults={'nom': 'STKCAT6 Other Co'})[0]

        # Catégorie GLOBALE typée structure (celle que le seeder pose).
        cls.cat_globale = Categorie.objects.create(
            company=None, nom='STKCAT6 Structures',
            ordre=10,
            type_equipement=Categorie.TypeEquipement.STRUCTURE)
        # Catégorie de la société, typée structure elle aussi.
        cls.cat_societe = Categorie.objects.create(
            company=cls.company, nom='STKCAT6 Pergolas',
            ordre=20,
            type_equipement=Categorie.TypeEquipement.STRUCTURE)
        # Catégorie d'une AUTRE société, même type.
        cls.cat_autre = Categorie.objects.create(
            company=cls.other_company, nom='STKCAT6 Structures voisines',
            ordre=10,
            type_equipement=Categorie.TypeEquipement.STRUCTURE)
        # Catégorie NON typée (le cas historique) — ne doit jamais remonter.
        cls.cat_non_typee = Categorie.objects.create(
            company=cls.company, nom='STKCAT6 Divers', ordre=30)

        cls.produit_global = Produit.objects.create(
            company=None, nom='Structures acier (global)',
            categorie=cls.cat_globale, prix_vente=Decimal('500'))
        cls.produit_societe = Produit.objects.create(
            company=cls.company, nom='Pergola acier 4x3',
            categorie=cls.cat_societe, prix_vente=Decimal('18000'))
        cls.produit_autre = Produit.objects.create(
            company=cls.other_company, nom='Pergola de la société voisine',
            categorie=cls.cat_autre, prix_vente=Decimal('19000'))
        cls.produit_archive = Produit.objects.create(
            company=cls.company, nom='Pergola retirée du catalogue',
            categorie=cls.cat_societe, prix_vente=Decimal('1'),
            is_archived=True)
        cls.produit_sans_prix = Produit.objects.create(
            company=cls.company, nom='Pergola prix à renseigner',
            categorie=cls.cat_societe, prix_vente=Decimal('0'))
        cls.produit_non_typee = Produit.objects.create(
            company=cls.company, nom='Visserie diverse',
            categorie=cls.cat_non_typee, prix_vente=Decimal('50'))


class TestCategoriesParType(STKCAT6Base):
    def test_rend_les_categories_de_la_societe_et_les_globales(self):
        noms = [c.nom for c in categories_par_type(self.company, 'structure')]
        self.assertIn('STKCAT6 Structures', noms)   # globale (company NULL)
        self.assertIn('STKCAT6 Pergolas', noms)     # celle de la société

    def test_jamais_la_categorie_d_une_autre_societe(self):
        noms = [c.nom for c in categories_par_type(self.company, 'structure')]
        self.assertNotIn('STKCAT6 Structures voisines', noms)

    def test_jamais_une_categorie_non_typee(self):
        noms = [c.nom for c in categories_par_type(self.company, 'structure')]
        self.assertNotIn('STKCAT6 Divers', noms)

    def test_ordre_categorie_puis_nom(self):
        cats = categories_par_type(self.company, 'structure')
        ordres = [c.ordre for c in cats]
        self.assertEqual(ordres, sorted(ordres))

    def test_type_vide_rend_une_liste_vide(self):
        self.assertEqual(categories_par_type(self.company, ''), [])
        self.assertEqual(categories_par_type(self.company, None), [])

    def test_type_inconnu_rend_une_liste_vide(self):
        self.assertEqual(
            categories_par_type(self.company, 'nimporte-quoi'), [])


class TestProduitsParTypeEquipement(STKCAT6Base):
    def _noms(self, **kwargs):
        return [p.nom for p in produits_par_type_equipement(
            self.company, 'structure', **kwargs)]

    def test_le_produit_global_est_rendu(self):
        self.assertIn('Structures acier (global)', self._noms())

    def test_le_produit_de_la_societe_est_rendu(self):
        self.assertIn('Pergola acier 4x3', self._noms())

    def test_jamais_le_produit_d_une_autre_societe(self):
        self.assertNotIn('Pergola de la société voisine', self._noms())

    def test_jamais_un_produit_archive(self):
        self.assertNotIn('Pergola retirée du catalogue', self._noms())

    def test_jamais_un_produit_d_une_categorie_non_typee(self):
        self.assertNotIn('Visserie diverse', self._noms())

    def test_avec_prix_par_defaut_ecarte_les_fiches_sans_prix(self):
        self.assertNotIn('Pergola prix à renseigner', self._noms())

    def test_avec_prix_false_rend_aussi_les_fiches_sans_prix(self):
        self.assertIn('Pergola prix à renseigner',
                      self._noms(avec_prix=False))

    def test_ordre_categorie_puis_nom(self):
        """La catégorie d'ordre 10 (globale) passe AVANT celle d'ordre 20.

        Comparaison sur les deux produits DE CE TEST uniquement : les autres
        lignes éventuelles du catalogue de test n'ont pas à peser sur une
        garde d'ordre (et un tri SQL n'a pas la même collation que ``sorted``
        de Python sur des libellés accentués)."""
        noms = self._noms()
        self.assertLess(noms.index('Structures acier (global)'),
                        noms.index('Pergola acier 4x3'))

    def test_type_vide_rend_une_liste_vide(self):
        self.assertEqual(
            produits_par_type_equipement(self.company, ''), [])
        self.assertEqual(
            produits_par_type_equipement(self.company, None), [])

    def test_la_categorie_est_prechargee(self):
        """``select_related('categorie')`` — lire le type d'un produit rendu
        ne doit coûter AUCUNE requête supplémentaire."""
        produits = produits_par_type_equipement(self.company, 'structure')
        self.assertTrue(produits)
        with self.assertNumQueries(0):
            for produit in produits:
                self.assertEqual(produit.categorie.type_equipement,
                                 'structure')
