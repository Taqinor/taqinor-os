"""NTDATA19 — dédoublonnage fournisseurs & produits + fusion supervisée.

Couvre le critère d'acceptation :
  * deux fournisseurs au MÊME ICE remontent, puis fusionnent SANS PERTE de
    mouvements de stock ;
  * deux produits à la même référence remontent ;
  * le doublon est ARCHIVÉ (jamais supprimé) et tracé ;
  * les quantités de stock ne sont JAMAIS additionnées à la fusion ;
  * le scoping société ;
  * aucun prix d'achat ne sort des détecteurs.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.dataquality import services
from apps.dataquality.dedoublonnage import POIDS_CRITERES
from apps.stock.models import (
    Categorie, Fournisseur, MouvementStock, Produit,
)
from apps.stock.services import merge_fournisseurs, merge_produits
from authentication.models import Company

User = get_user_model()


class DoublonsFournisseursTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA19 SA',
                                             slug='ntdata19-sa')
        cls.autre = Company.objects.create(nom='NTDATA19 Autre',
                                           slug='ntdata19-autre')
        cls.user = User.objects.create_user(
            username='ntdata19_u', password='x', company=cls.company,
            role_legacy='admin')

    def test_meme_ice_remonte(self):
        a = Fournisseur.objects.create(company=self.company, nom='Alpha SARL',
                                       ice='001234567000089')
        b = Fournisseur.objects.create(company=self.company, nom='ALPHA',
                                       ice='001234567000089')
        Fournisseur.objects.create(company=self.company, nom='Zeta',
                                   ice='009999999000011')
        groupes = services.doublons_fournisseurs(self.company, self.user)
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0]['ids'], sorted([a.id, b.id]))
        self.assertEqual(groupes[0]['score'], POIDS_CRITERES['ice'])

    def test_aucun_prix_d_achat_dans_le_detecteur(self):
        Fournisseur.objects.create(company=self.company, nom='Alpha',
                                   ice='001234567000089')
        Fournisseur.objects.create(company=self.company, nom='Alpha2',
                                   ice='001234567000089')
        groupes = services.doublons_fournisseurs(self.company, self.user)
        texte = str(groupes)
        self.assertNotIn('prix_achat', texte)
        self.assertNotIn('valeur_achat', texte)

    def test_scoping_societe(self):
        Fournisseur.objects.create(company=self.company, nom='Alpha',
                                   ice='001234567000089')
        Fournisseur.objects.create(company=self.autre, nom='Alpha',
                                   ice='001234567000089')
        self.assertEqual(
            services.doublons_fournisseurs(self.company, self.user), [])

    def test_fournisseur_archive_exclu(self):
        Fournisseur.objects.create(company=self.company, nom='Alpha',
                                   ice='001234567000089')
        Fournisseur.objects.create(company=self.company, nom='Alpha2',
                                   ice='001234567000089', is_archived=True)
        self.assertEqual(
            services.doublons_fournisseurs(self.company, self.user), [])

    def test_fusion_sans_perte_de_mouvements(self):
        survivant = Fournisseur.objects.create(
            company=self.company, nom='Alpha', ice='001234567000089')
        doublon = Fournisseur.objects.create(
            company=self.company, nom='Alpha SARL', ice='001234567000089',
            email='contact@alpha.ma')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', prix_achat=Decimal('100'),
            prix_vente=Decimal('150'), quantite_stock=5,
            fournisseur=doublon)
        mouvement = MouvementStock.objects.create(
            company=self.company, produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=5, quantite_avant=0, quantite_apres=5)
        rapport = merge_fournisseurs(survivant, [doublon], self.user)

        produit.refresh_from_db()
        self.assertEqual(produit.fournisseur_id, survivant.pk)
        # Le mouvement n'a pas bougé de produit : rien n'est perdu.
        self.assertTrue(
            MouvementStock.objects.filter(pk=mouvement.pk).exists())
        # Le doublon est ARCHIVÉ, jamais supprimé.
        doublon.refresh_from_db()
        self.assertTrue(Fournisseur.objects.filter(pk=doublon.pk).exists())
        self.assertTrue(doublon.is_archived)
        self.assertEqual(doublon.custom_data['fusionne_dans'], survivant.pk)
        # Champ vide du survivant complété depuis le doublon.
        survivant.refresh_from_db()
        self.assertEqual(survivant.email, 'contact@alpha.ma')
        self.assertEqual(rapport['absorbes'], [doublon.pk])
        self.assertIn('stock.Produit.fournisseur', rapport['repointes'])

    def test_fusion_cross_tenant_refusee(self):
        survivant = Fournisseur.objects.create(company=self.company,
                                               nom='Alpha')
        etranger = Fournisseur.objects.create(company=self.autre,
                                              nom='Ailleurs')
        rapport = merge_fournisseurs(survivant, [etranger], self.user)
        self.assertEqual(rapport['absorbes'], [])


class DoublonsProduitsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA19 P',
                                             slug='ntdata19-p')
        cls.user = User.objects.create_user(
            username='ntdata19_p', password='x', company=cls.company,
            role_legacy='admin')
        cls.categorie = Categorie.objects.create(company=cls.company,
                                                 nom='Panneaux')

    def _produit(self, nom, **kw):
        defaults = dict(company=self.company, nom=nom,
                        prix_achat=Decimal('100'), prix_vente=Decimal('150'),
                        quantite_stock=0, categorie=self.categorie)
        defaults.update(kw)
        return Produit.objects.create(**defaults)

    def test_meme_reference_remonte(self):
        a = self._produit('Panneau 550 Wc', sku='PAN-550')
        b = self._produit('Panneau 550W', sku='pan-550 ')
        self._produit('Onduleur', sku='OND-5K')
        groupes = services.doublons_produits(self.company, self.user)
        self.assertEqual(len(groupes), 1)
        self.assertEqual(groupes[0]['ids'], sorted([a.id, b.id]))
        self.assertIn('reference', groupes[0]['motifs'])
        self.assertEqual(groupes[0]['score'], POIDS_CRITERES['reference'])

    def test_designation_approchee(self):
        a = self._produit('Panneau Photovoltaique 550')
        b = self._produit('Panneau Photovoltaïque 550')
        groupes = services.doublons_produits(self.company, self.user)
        self.assertEqual(groupes[0]['ids'], sorted([a.id, b.id]))
        self.assertEqual(groupes[0]['motifs'], ['nom'])

    def test_fusion_n_additionne_jamais_les_quantites(self):
        survivant = self._produit('Panneau', sku='PAN-550', quantite_stock=10)
        doublon = self._produit('Panneau bis', sku='pan-550',
                                quantite_stock=7, marque='Longi')
        merge_produits(survivant, [doublon], self.user)
        survivant.refresh_from_db()
        doublon.refresh_from_db()
        # Un stock est un fait physique constaté, pas une somme de fiches.
        self.assertEqual(survivant.quantite_stock, 10)
        self.assertTrue(doublon.is_archived)
        # Champ d'identité vide complété (marque), prix d'achat JAMAIS migré.
        self.assertEqual(survivant.marque, 'Longi')

    def test_produit_archive_exclu_de_la_detection(self):
        # `sku` est UNIQUE par société en base (unique_together company+sku) :
        # le doublon de référence se joue donc, comme dans les tests ci-dessus,
        # sur une VARIANTE de casse/espaces — que le détecteur normalise vers
        # la même clé. Archivé, il ne doit pas remonter.
        self._produit('Panneau', sku='PAN-550')
        self._produit('Panneau bis', sku='pan-550 ', is_archived=True)
        self.assertEqual(services.doublons_produits(self.company, self.user),
                         [])


class FusionViaDataqualityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA19 DQ',
                                             slug='ntdata19-dq')
        cls.autre = Company.objects.create(nom='NTDATA19 DQ2',
                                           slug='ntdata19-dq2')
        cls.user = User.objects.create_user(
            username='ntdata19_dq', password='x', company=cls.company,
            role_legacy='admin')

    def test_fusion_fournisseurs(self):
        survivant = Fournisseur.objects.create(company=self.company, nom='A')
        doublon = Fournisseur.objects.create(company=self.company, nom='B')
        rapport = services.fusionner_fournisseurs(
            self.company, self.user, survivant.pk, [doublon.pk])
        self.assertEqual(rapport['absorbes'], [doublon.pk])

    def test_fusion_produits(self):
        survivant = Produit.objects.create(
            company=self.company, nom='A', prix_achat=Decimal('1'),
            prix_vente=Decimal('2'), quantite_stock=0)
        doublon = Produit.objects.create(
            company=self.company, nom='B', prix_achat=Decimal('1'),
            prix_vente=Decimal('2'), quantite_stock=0)
        rapport = services.fusionner_produits(
            self.company, self.user, survivant.pk, [doublon.pk])
        self.assertEqual(rapport['absorbes'], [doublon.pk])

    def test_survivant_d_une_autre_societe_refuse(self):
        etranger = Fournisseur.objects.create(company=self.autre, nom='X')
        doublon = Fournisseur.objects.create(company=self.company, nom='B')
        with self.assertRaises(ValueError) as ctx:
            services.fusionner_fournisseurs(
                self.company, self.user, etranger.pk, [doublon.pk])
        self.assertIn('introuvable', str(ctx.exception))
