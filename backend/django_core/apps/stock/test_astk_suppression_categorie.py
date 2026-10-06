"""ASTK82 — supprimer une catégorie utilisée est refusé (C-ASTK-017).

Sonde CAT-6 : DELETE → 204, ``produit.categorie_id`` mis à NULL en silence et
le profil saisonnier de la catégorie supprimé en cascade.
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie, ProfilSaisonnier, Produit
from authentication.models import Company, User

_seq = itertools.count(1)


class SuppressionCategorieTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK82 {n}', slug=f'astk82-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk82_admin_{n}', password='x',
            email=f'astk82-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Structures',
            type_equipement='structure')

    def test_categorie_utilisee_refusee(self):
        produit = Produit.objects.create(
            company=self.company, nom='Pergola alu',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            categorie=self.categorie)
        profil = ProfilSaisonnier.objects.create(
            company=self.company, categorie=self.categorie,
            mois_debut=3, mois_fin=6, seuil_min=2)

        reponse = self.api.delete(
            f'/api/django/stock/categories/{self.categorie.pk}/')

        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('Catégorie utilisée par 1 produit :',
                      reponse.json()['detail'])
        # persistance : relu en base
        produit.refresh_from_db()
        self.assertEqual(produit.categorie_id, self.categorie.pk)
        self.assertTrue(Categorie.objects.filter(
            pk=self.categorie.pk).exists())
        self.assertTrue(ProfilSaisonnier.objects.filter(
            pk=profil.pk).exists())

    def test_categorie_avec_produit_archive_refusee_aussi(self):
        Produit.objects.create(
            company=self.company, nom='Ancienne pergola',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            categorie=self.categorie, is_archived=True)

        reponse = self.api.delete(
            f'/api/django/stock/categories/{self.categorie.pk}/')

        self.assertEqual(reponse.status_code, 400, reponse.content)

    def test_categorie_sans_produit_supprimable(self):
        reponse = self.api.delete(
            f'/api/django/stock/categories/{self.categorie.pk}/')

        self.assertEqual(reponse.status_code, 204, reponse.content)
        self.assertFalse(Categorie.objects.filter(
            pk=self.categorie.pk).exists())
