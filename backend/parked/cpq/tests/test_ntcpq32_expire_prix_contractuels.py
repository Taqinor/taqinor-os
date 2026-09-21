"""NTCPQ32 — Job planifié « Expiration des prix contractuels »."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cpq.models import PrixContractuel
from apps.cpq.scheduled import expire_prix_contractuels
from apps.records.models import Activity
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory, UserFactory


class TestExpirePrixContractuels(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.client_obj = ClientFactory(company=self.company)
        self.produit = ProduitFactory(company=self.company)

    def test_prix_expire_genere_une_activite(self):
        hier = timezone.localdate() - timedelta(days=1)
        prix = PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('999.00'),
            date_fin=hier, created_by=self.user)
        count = expire_prix_contractuels()
        self.assertEqual(count, 1)
        self.assertEqual(Activity.objects.filter(
            object_id=prix.id, summary='Prix contractuel expiré').count(), 1)
        activite = Activity.objects.get(
            object_id=prix.id, summary='Prix contractuel expiré')
        self.assertEqual(activite.assigned_to_id, self.user.id)

    def test_prix_non_expire_aucune_activite(self):
        demain = timezone.localdate() + timedelta(days=1)
        PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('999.00'),
            date_fin=demain, created_by=self.user)
        self.assertEqual(expire_prix_contractuels(), 0)
        self.assertEqual(Activity.objects.count(), 0)

    def test_prix_sans_date_fin_jamais_expire(self):
        PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('999.00'),
            created_by=self.user)
        self.assertEqual(expire_prix_contractuels(), 0)

    def test_idempotent_deuxieme_run_ne_double_pas(self):
        hier = timezone.localdate() - timedelta(days=1)
        PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('999.00'),
            date_fin=hier, created_by=self.user)
        first = expire_prix_contractuels()
        second = expire_prix_contractuels()
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(Activity.objects.filter(
            summary='Prix contractuel expiré').count(), 1)
