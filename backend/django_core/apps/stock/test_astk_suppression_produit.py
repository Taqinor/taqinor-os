"""ASTK81 — « Supprimer » un produit référencé l'ARCHIVE (C-ASTK-017).

Sonde CAT-1 : DELETE → 204, la réservation de chantier disparaissait en
cascade et la ligne de BCF perdait son produit (SET_NULL). Les modèles des
autres apps sont lus par ``apps.get_model`` (aucun import de leurs models).
"""
import itertools
from decimal import Decimal

from django.apps import apps
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from authentication.models import Company, CustomUser as User

_seq = itertools.count(1)


class SuppressionProduitTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK81 {n}', slug=f'astk81-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk81_admin_{n}', password='x',
            email=f'astk81-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK81')

    def _produit(self, nom, archive=False):
        return Produit.objects.create(
            company=self.company, nom=nom, prix_achat=Decimal('100'),
            prix_vente=Decimal('150'), is_archived=archive)

    def _reservation(self, produit):
        Client = apps.get_model('crm', 'Client')
        Installation = apps.get_model('installations', 'Installation')
        StockReservation = apps.get_model('installations', 'StockReservation')
        n = next(_seq)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASTK81',
            email=f'astk81-cli-{n}@example.invalid')
        inst = Installation.objects.create(
            company=self.company, reference=f'CHT-ASTK81-{n}', client=client,
            type_installation='residentiel')
        return StockReservation.objects.create(
            company=self.company, installation=inst, produit=produit,
            quantite=2)

    def _ligne_bcf(self, produit):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BC-ASTK81-{next(_seq)}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        return LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=produit, quantite=1,
            prix_achat_unitaire=Decimal('100'))

    def test_destroy_archive_si_reservation(self):
        produit = self._produit('Panneau réservé')
        resa = self._reservation(produit)
        ligne = self._ligne_bcf(produit)

        reponse = self.api.delete(f'/api/django/stock/produits/{produit.pk}/')

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertTrue(reponse.json()['archived'])
        self.assertIn('1 réservation', reponse.json()['detail'])
        self.assertNotIn('0 mouvement', reponse.json()['detail'])
        produit.refresh_from_db()
        self.assertTrue(produit.is_archived)
        # persistance : relu en base
        resa.refresh_from_db()
        self.assertEqual(resa.produit_id, produit.pk)
        ligne.refresh_from_db()
        self.assertEqual(ligne.produit_id, produit.pk)

    def test_force_delete_archive_si_ligne_bcf(self):
        produit = self._produit('Onduleur commandé', archive=True)
        ligne = self._ligne_bcf(produit)

        reponse = self.api.delete(
            f'/api/django/stock/produits/{produit.pk}/force-delete/')

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertTrue(reponse.json()['archived'])
        self.assertIn('ligne', reponse.json()['detail'])
        self.assertTrue(Produit.objects.filter(pk=produit.pk).exists())
        ligne.refresh_from_db()
        self.assertEqual(ligne.produit_id, produit.pk)

    def test_destroy_supprime_si_aucune_reference(self):
        produit = self._produit('Produit jetable')

        reponse = self.api.delete(f'/api/django/stock/produits/{produit.pk}/')

        self.assertEqual(reponse.status_code, 204, reponse.content)
        self.assertFalse(Produit.objects.filter(pk=produit.pk).exists())
