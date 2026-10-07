"""ASTK47 (C-ASTK-009) — `decouper_produit` verrouille la source avant de lire son stock.

Constat MVT-16 : avec une instance du produit source lue à 50 alors que la
base est à 5 (seconde requête qui a lu avant le commit de la première), une
découpe de 10 était ACCEPTÉE : stock final 40, mouvement avant=50 après=40 —
45 unités fantômes. Désormais la source est relue sous
`verrouiller_produit` (patron AUD216, comme la cible) : refus « Stock
insuffisant (5 disponible) », rien n'est écrit.

Run :
    python manage.py test apps.stock.test_astk_decoupe_verrou
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import decouper_produit

User = get_user_model()


class DecoupeVerrouTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK47 Co', slug='astk47-co')
        self.user = User.objects.create_user(
            username='astk47-user', password='x', company=self.company,
            role_legacy='admin')
        self.source = Produit.objects.create(
            company=self.company, nom='Touret ASTK47', sku='SRC-ASTK47',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'),
            quantite_stock=50)
        self.cible = Produit.objects.create(
            company=self.company, nom='Coupe ASTK47', sku='CIB-ASTK47',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'),
            quantite_stock=0)

    def test_instance_perimee_stock_insuffisant_refuse(self):
        perimee = Produit.objects.get(pk=self.source.pk)  # lue à 50
        Produit.objects.filter(pk=self.source.pk).update(quantite_stock=5)
        self.assertEqual(perimee.quantite_stock, 50)
        with self.assertRaises(ValueError) as ctx:
            decouper_produit(
                company=self.company, produit_source=perimee,
                quantite_consommee=10, produit_cible=self.cible,
                quantite_produite=10, user=self.user)
        self.assertIn('Stock insuffisant', str(ctx.exception))
        self.assertIn('(5 disponible)', str(ctx.exception))
        self.source.refresh_from_db()
        self.cible.refresh_from_db()
        self.assertEqual(self.source.quantite_stock, 5)
        self.assertEqual(self.cible.quantite_stock, 0)
        self.assertFalse(MouvementStock.objects.filter(
            company=self.company).exists())

    def test_instance_perimee_arithmetique_sur_la_valeur_reelle(self):
        perimee = Produit.objects.get(pk=self.source.pk)  # lue à 50
        Produit.objects.filter(pk=self.source.pk).update(quantite_stock=30)
        decouper_produit(
            company=self.company, produit_source=perimee,
            quantite_consommee=10, produit_cible=self.cible,
            quantite_produite=10, user=self.user)
        self.source.refresh_from_db()
        self.assertEqual(self.source.quantite_stock, 20)
        sortie = MouvementStock.objects.get(
            produit=self.source,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(
            (sortie.quantite_avant, sortie.quantite_apres), (30, 20))
