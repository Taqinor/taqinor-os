"""NTDATA3 — datasets BI stock & achats (produits / mouvements / BCF).

Couvre :
  * les trois datasets sont enregistrés (via `apps.py` ready()) ;
  * scoping société ;
  * `est_low_stock` suit la définition historique (stock brut vs seuil) ;
  * `montant` d'un BCF = somme quantité × prix d'achat unitaire ;
  * les champs d'ACHAT sont MASQUÉS pour un lecteur sans `prix_achat_voir`
    (gated_fields AUD801) — dans le select ET dans les agrégats.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.achats.models import (
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
)
from apps.roles.models import Role
from apps.stock.bi_datasets import (
    BCF_DATASET, MOUVEMENTS_DATASET, PRODUITS_DATASET,
)
from apps.stock.models import Categorie, Fournisseur, MouvementStock, Produit
from authentication.models import Company
from core import data_explorer

User = get_user_model()


class StockBiDatasetsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntdata3-co', defaults={'nom': 'NTDATA3 Co'})[0]
        self.autre = Company.objects.get_or_create(
            slug='ntdata3-autre', defaults={'nom': 'NTDATA3 Autre'})[0]
        # Superuser → voit les prix d'achat (can_view_buy_prices True).
        self.admin = User.objects.create_superuser(
            username='ntdata3_admin', password='x', email='a@b.c')
        self.admin.company = self.company
        self.admin.save(update_fields=['company'])
        # Utilisateur avec un rôle fin SANS `prix_achat_voir` → masqué.
        role = Role.objects.create(
            company=self.company, nom='NTDATA3 Vendeur', permissions=[])
        self.vendeur = User.objects.create_user(
            username='ntdata3_vendeur', password='x', company=self.company,
            role=role)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Panneaux')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='FournisseurNTDATA3')

    def _produit(self, **kw):
        defaults = dict(
            company=self.company, nom='P-NTDATA3', prix_achat=Decimal('100.00'),
            prix_vente=Decimal('150.00'), quantite_stock=10,
            categorie=self.categorie)
        defaults.update(kw)
        return Produit.objects.create(**defaults)

    def test_datasets_enregistres(self):
        noms = {d['name'] for d in data_explorer.list_datasets()}
        self.assertIn(PRODUITS_DATASET, noms)
        self.assertIn(MOUVEMENTS_DATASET, noms)
        self.assertIn(BCF_DATASET, noms)

    def test_produits_scope_societe(self):
        self._produit()
        Produit.objects.create(
            company=self.autre, nom='P-AUTRE', prix_achat=Decimal('1'),
            prix_vente=Decimal('2'), quantite_stock=1)
        lignes = data_explorer.run_query(
            PRODUITS_DATASET, self.company, self.admin, {'select': ['id']})
        self.assertEqual(len(lignes), 1)

    def test_est_low_stock(self):
        bas = self._produit(nom='P-BAS', quantite_stock=2, seuil_alerte=5)
        haut = self._produit(nom='P-HAUT', quantite_stock=50, seuil_alerte=5)
        sans_seuil = self._produit(nom='P-SANS', quantite_stock=0,
                                   seuil_alerte=0)
        lignes = {
            r['id']: r['est_low_stock']
            for r in data_explorer.run_query(
                PRODUITS_DATASET, self.company, self.admin,
                {'select': ['id', 'est_low_stock']})
        }
        self.assertTrue(lignes[bas.id])
        self.assertFalse(lignes[haut.id])
        # Seuil à 0 ⇒ alerte désactivée (comportement historique).
        self.assertFalse(lignes[sans_seuil.id])

    def test_valeur_achat_visible_pour_admin(self):
        self._produit(quantite_stock=4, prix_achat=Decimal('25.00'))
        lignes = data_explorer.run_query(
            PRODUITS_DATASET, self.company, self.admin,
            {'select': ['prix_achat', 'valeur_achat']})
        self.assertEqual(lignes[0]['valeur_achat'], Decimal('100.00'))

    def test_prix_achat_masque_sans_permission(self):
        self._produit(quantite_stock=4, prix_achat=Decimal('25.00'))
        lignes = data_explorer.run_query(
            PRODUITS_DATASET, self.company, self.vendeur,
            {'select': ['id', 'prix_achat', 'valeur_achat']})
        self.assertNotIn('prix_achat', lignes[0])
        self.assertNotIn('valeur_achat', lignes[0])

    def test_prix_achat_masque_aussi_dans_un_agregat(self):
        self._produit(quantite_stock=4, prix_achat=Decimal('25.00'))
        lignes = data_explorer.run_query(
            PRODUITS_DATASET, self.company, self.vendeur, {
                'group_by': ['marque'],
                'aggregates': [
                    {'alias': 'total', 'fn': 'sum', 'field': 'valeur_achat'}],
            })
        self.assertNotIn('total', lignes[0])

    def test_mouvements_group_by_type(self):
        produit = self._produit()
        MouvementStock.objects.create(
            company=self.company, produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=5, quantite_avant=0, quantite_apres=5)
        MouvementStock.objects.create(
            company=self.company, produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=2, quantite_avant=5, quantite_apres=3)
        lignes = data_explorer.run_query(
            MOUVEMENTS_DATASET, self.company, self.admin, {
                'group_by': ['type'],
                'aggregates': [
                    {'alias': 'q', 'fn': 'sum', 'field': 'quantite'}],
            })
        par_type = {r['type']: r['q'] for r in lignes}
        self.assertEqual(par_type[MouvementStock.TypeMouvement.ENTREE], 5)
        self.assertEqual(par_type[MouvementStock.TypeMouvement.SORTIE], 2)

    def test_bcf_montant_somme_des_lignes(self):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTDATA3',
            fournisseur=self.fournisseur)
        produit = self._produit()
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=produit, quantite=3,
            prix_achat_unitaire=Decimal('100.00'))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=produit, quantite=2,
            prix_achat_unitaire=Decimal('50.00'))
        lignes = data_explorer.run_query(
            BCF_DATASET, self.company, self.admin,
            {'select': ['id', 'fournisseur__nom', 'montant']})
        ligne = next(r for r in lignes if r['id'] == bcf.id)
        self.assertEqual(ligne['montant'], Decimal('400.00'))
        self.assertEqual(ligne['fournisseur__nom'], 'FournisseurNTDATA3')

    def test_bcf_montant_masque_sans_permission(self):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTDATA3-2',
            fournisseur=self.fournisseur)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self._produit(), quantite=1,
            prix_achat_unitaire=Decimal('10.00'))
        lignes = data_explorer.run_query(
            BCF_DATASET, self.company, self.vendeur,
            {'select': ['id', 'montant']})
        self.assertNotIn('montant', lignes[0])
