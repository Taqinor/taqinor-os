"""NTCRM6 — Snapshots hebdomadaires du forecast (idempotents)."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.management.commands.snapshot_forecast_hebdo import (
    snapshot_forecast_hebdo,
)
from apps.crm.models import ForecastEntry, ForecastSnapshot, Lead
from apps.roles.models import Role

User = get_user_model()


class SnapshotForecastHebdoTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM6', slug='taqinor-ntcrm6')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.commercial = User.objects.create_user(
            username='com_ntcrm6', password='x', company=self.company, role=self.role)
        lead = Lead.objects.create(company=self.company, nom='Lead S1', owner=self.commercial)
        ForecastEntry.objects.create(
            company=self.company, lead=lead,
            categorie=ForecastEntry.Categorie.COMMIT, montant_prevu=Decimal('5000'))

    def test_deux_executions_meme_semaine_pas_de_doublon(self):
        now = timezone.now()
        nb1 = snapshot_forecast_hebdo(now=now)
        self.assertGreater(nb1, 0)
        count_after_first = ForecastSnapshot.objects.filter(company=self.company).count()
        nb2 = snapshot_forecast_hebdo(now=now)
        self.assertGreater(nb2, 0)
        count_after_second = ForecastSnapshot.objects.filter(company=self.company).count()
        self.assertEqual(count_after_first, count_after_second)

    def test_historique_4_semaines_evolution_correcte(self):
        base = timezone.now()
        montants_hebdo = [Decimal('5000'), Decimal('7000'), Decimal('9000'), Decimal('11000')]
        for i, montant in enumerate(montants_hebdo):
            ForecastEntry.objects.filter(company=self.company).update(montant_prevu=montant)
            snapshot_forecast_hebdo(now=base + timedelta(weeks=i))

        snapshots = list(
            ForecastSnapshot.objects.filter(
                company=self.company, categorie='commit', owner__isnull=True,
            ).order_by('semaine_iso'))
        self.assertEqual(len(snapshots), 4)
        self.assertEqual(
            [s.montant_total for s in snapshots],
            montants_hebdo)
