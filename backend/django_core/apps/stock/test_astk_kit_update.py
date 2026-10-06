"""ASTK96 — un PUT de kit ne remet plus ``taux_perte_pct`` à zéro.

Sonde CAT-12 : ``KitProduitSerializer.update`` supprimait puis recréait les
composants avec les seuls champs du serializer → perte 5 → 0.00.
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import KitComposant, KitProduit, Produit
from apps.stock.services import snapshot_revision_kit
from authentication.models import Company, User

_seq = itertools.count(1)


class KitUpdateTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK96 {n}', slug=f'astk96-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk96_admin_{n}', password='x',
            email=f'astk96-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.p1 = Produit.objects.create(
            company=self.company, nom='Câble 6mm', sku='CAB-6',
            prix_vente=Decimal('10'))
        self.p2 = Produit.objects.create(
            company=self.company, nom='Connecteur', sku='CON-1',
            prix_vente=Decimal('5'))
        self.kit = KitProduit.objects.create(
            company=self.company, nom='Kit câblage')
        KitComposant.objects.create(
            kit=self.kit, produit=self.p1, quantite=Decimal('2'),
            taux_perte_pct=Decimal('5.00'))
        snapshot_revision_kit(self.kit)

    def _put(self, composants):
        return self.api.put(
            f'/api/django/stock/kits/{self.kit.pk}/',
            {'nom': 'Kit câblage', 'composants': composants}, format='json')

    def test_put_identique_garde_taux_perte(self):
        revisions_avant = self.kit.revisions.count()

        reponse = self._put([{'produit': self.p1.pk, 'quantite': '2'}])

        self.assertEqual(reponse.status_code, 200, reponse.content)
        composant = KitComposant.objects.get(kit=self.kit, produit=self.p1)
        self.assertEqual(composant.taux_perte_pct, Decimal('5.00'))
        # snapshot comparé APRÈS préservation : aucune révision « identique »
        self.assertEqual(self.kit.revisions.count(), revisions_avant)

    def test_composant_retire_supprime_nouveau_naît_a_zero(self):
        reponse = self._put([{'produit': self.p2.pk, 'quantite': '1'}])

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertFalse(KitComposant.objects.filter(
            kit=self.kit, produit=self.p1).exists())
        nouveau = KitComposant.objects.get(kit=self.kit, produit=self.p2)
        self.assertEqual(nouveau.taux_perte_pct, Decimal('0'))
