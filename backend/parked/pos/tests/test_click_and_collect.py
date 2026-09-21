"""XPOS15 — Click-and-collect (retrait en magasin).

Couvre : une commande retrait traverse les 3 statuts (à préparer → prêt →
retiré) avec décrément stock à la préparation, la remise exige le bon code,
stock exact, garde multi-société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services
from apps.pos.models import CommandeRetrait, LigneCommandeRetrait
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class ClickAndCollectTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos15', 'XPOS15 Co')
        self.user = make_user(self.co, 'magasinier-xpos15')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Régulateur', prix_vente=Decimal('300'),
            prix_achat=Decimal('150'), quantite_stock=15, categorie=categorie)
        self.commande = CommandeRetrait.objects.create(
            company=self.co, reference='RET-000001', client=self.client_obj,
            created_by=self.user)
        LigneCommandeRetrait.objects.create(
            commande=self.commande, produit=self.produit, quantite=3)

    def test_marquer_pret_decremente_stock(self):
        services.marquer_pret(commande=self.commande, user=self.user)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.statut, CommandeRetrait.Statut.PRET)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 12)

    def test_cannot_marquer_pret_twice(self):
        services.marquer_pret(commande=self.commande, user=self.user)
        with self.assertRaises(services.CommandeRetraitError):
            services.marquer_pret(commande=self.commande, user=self.user)

    def test_remettre_requires_correct_code(self):
        services.marquer_pret(commande=self.commande, user=self.user)
        self.commande.refresh_from_db()
        with self.assertRaises(services.CommandeRetraitError):
            services.remettre_commande(
                commande=self.commande, code_saisi='WRONG', user=self.user)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.statut, CommandeRetrait.Statut.PRET)

    def test_remettre_with_correct_code(self):
        services.marquer_pret(commande=self.commande, user=self.user)
        self.commande.refresh_from_db()
        services.remettre_commande(
            commande=self.commande, code_saisi=self.commande.code_retrait,
            user=self.user)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.statut, CommandeRetrait.Statut.RETIRE)
        self.assertIsNotNone(self.commande.date_retrait)

    def test_cannot_remettre_before_pret(self):
        with self.assertRaises(services.CommandeRetraitError):
            services.remettre_commande(
                commande=self.commande, code_saisi=self.commande.code_retrait,
                user=self.user)

    def test_code_retrait_case_insensitive(self):
        services.marquer_pret(commande=self.commande, user=self.user)
        self.commande.refresh_from_db()
        services.remettre_commande(
            commande=self.commande,
            code_saisi=self.commande.code_retrait.lower(),
            user=self.user)
        self.commande.refresh_from_db()
        self.assertEqual(self.commande.statut, CommandeRetrait.Statut.RETIRE)
