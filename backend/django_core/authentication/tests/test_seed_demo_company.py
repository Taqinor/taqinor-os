"""Tests de la commande ``seed_demo_company`` (NTDMO1-5)."""
from django.core.management import call_command
from django.test import TestCase, override_settings

from authentication.models import Company, CustomUser


@override_settings(DEBUG=True)
class SeedDemoCompanyNTDMO1Test(TestCase):
    SLUG = 'taqinor-demo-full'

    def test_creates_company_profile_users_and_marks_demo(self):
        call_command('seed_demo_company', verbosity=0)
        company = Company.objects.get(slug=self.SLUG)
        # NTDMO8 — la société est marquée démo.
        self.assertTrue(company.est_demo)
        self.assertFalse(company.mode_presentation_actif)
        # Profil complet avec identité légale placeholder.
        profile = company.profile
        self.assertTrue(profile.ice)
        self.assertTrue(profile.identifiant_fiscal)
        self.assertTrue(profile.rc)
        # Utilisateurs connus créés et protégés.
        admin = CustomUser.objects.get(username='demo_admin_full')
        self.assertTrue(admin.is_protected)
        self.assertTrue(admin.check_password('DemoFull@2026!'))
        self.assertTrue(
            CustomUser.objects.filter(username='demo_resp_full').exists())

    def test_never_collides_with_seed_demo_company(self):
        call_command('seed_demo_company', verbosity=0)
        self.assertFalse(Company.objects.filter(slug='taqinor-demo').exists())

    def test_idempotent_run_twice_stable_counts(self):
        call_command('seed_demo_company', verbosity=0)
        c1 = Company.objects.count()
        u1 = CustomUser.objects.count()
        call_command('seed_demo_company', verbosity=0)
        self.assertEqual(Company.objects.count(), c1)
        self.assertEqual(CustomUser.objects.count(), u1)

    @override_settings(DEBUG=False)
    def test_refused_outside_debug_without_force(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed_demo_company', verbosity=0)


@override_settings(DEBUG=True)
class SeedDemoLeadsNTDMO2Test(TestCase):
    SLUG = 'taqinor-demo-full'

    def setUp(self):
        call_command('seed_demo_company', verbosity=0)
        self.company = Company.objects.get(slug=self.SLUG)

    def test_lead_on_each_of_six_stages_and_lost(self):
        from apps.crm.models import Lead
        from apps.crm.stages import STAGES
        stages_present = set(
            Lead.objects.filter(company=self.company)
            .values_list('stage', flat=True))
        for key in STAGES:
            self.assertIn(key, stages_present, f'stage {key} manquant')
        lost = Lead.objects.filter(company=self.company, perdu=True)
        self.assertGreaterEqual(lost.count(), 3)
        # Les leads perdus portent un motif peuplé.
        self.assertTrue(all(bool(m) for m in lost.values_list(
            'motif_perte', flat=True)))

    def test_leads_dated_relative_to_now(self):
        from django.utils import timezone
        from apps.crm.models import Lead
        # Aucune date de création dans le futur, ~40 leads sur 12 mois.
        qs = Lead.objects.filter(company=self.company)
        self.assertGreaterEqual(qs.count(), 35)
        self.assertFalse(
            qs.filter(date_creation__gt=timezone.now()).exists())

    def test_some_future_relances(self):
        from django.utils import timezone
        from apps.crm.models import Lead
        self.assertTrue(
            Lead.objects.filter(
                company=self.company,
                relance_date__gte=timezone.now().date()).exists())


@override_settings(DEBUG=True)
class SeedDemoDevisNTDMO3Test(TestCase):
    SLUG = 'taqinor-demo-full'

    def setUp(self):
        call_command('seed_demo_company', verbosity=0)
        self.company = Company.objects.get(slug=self.SLUG)

    def test_devis_span_at_least_eight_months(self):
        from apps.ventes.models import Devis
        qs = Devis.objects.filter(company=self.company)
        self.assertGreaterEqual(qs.count(), 20)
        months = {(d.date_creation.year, d.date_creation.month) for d in qs}
        self.assertGreaterEqual(len(months), 8)

    def test_three_market_modes_present(self):
        from apps.ventes.models import Devis
        modes = set()
        for d in Devis.objects.filter(company=self.company):
            if d.etude_params:
                modes.add(d.etude_params.get('mode'))
            else:
                modes.add('residentiel')
        self.assertIn('residentiel', modes)
        self.assertIn('industriel', modes)
        self.assertIn('agricole', modes)

    def test_roughly_forty_percent_signed(self):
        from apps.ventes.models import Devis
        qs = Devis.objects.filter(company=self.company)
        signed = qs.filter(statut=Devis.Statut.ACCEPTE).count()
        self.assertGreaterEqual(signed, qs.count() * 0.3)

    def test_uses_reference_numbering(self):
        from apps.ventes.models import Devis
        refs = list(Devis.objects.filter(company=self.company)
                    .values_list('reference', flat=True))
        self.assertTrue(all(r.startswith('DEV-') for r in refs))
        self.assertEqual(len(refs), len(set(refs)))  # aucune collision


@override_settings(DEBUG=True)
class SeedDemoChantiersFacturesNTDMO4Test(TestCase):
    SLUG = 'taqinor-demo-full'

    def setUp(self):
        call_command('seed_demo_company', verbosity=0)
        self.company = Company.objects.get(slug=self.SLUG)

    def test_chantiers_created_some_receptionnes(self):
        from apps.installations.models import Installation
        qs = Installation.objects.filter(company=self.company)
        self.assertTrue(qs.exists())
        self.assertTrue(
            qs.filter(statut=Installation.Statut.RECEPTIONNE).exists())

    def test_aged_balance_has_three_plus_buckets(self):
        from django.utils import timezone
        from apps.ventes.models import Facture
        today = timezone.now().date()
        overdue = Facture.objects.filter(
            company=self.company, statut=Facture.Statut.EMISE,
            date_echeance__lt=today)
        buckets = set()
        for f in overdue:
            days = (today - f.date_echeance).days
            if days <= 30:
                buckets.add('0-30')
            elif days <= 60:
                buckets.add('31-60')
            elif days <= 90:
                buckets.add('61-90')
            else:
                buckets.add('90+')
        self.assertGreaterEqual(len(buckets), 3)

    def test_payment_mix(self):
        from apps.ventes.models import Facture, Paiement
        self.assertTrue(Facture.objects.filter(
            company=self.company, statut=Facture.Statut.PAYEE).exists())
        self.assertTrue(
            Paiement.objects.filter(company=self.company).exists())


@override_settings(DEBUG=True)
class SeedDemoSavStockNTDMO5Test(TestCase):
    SLUG = 'taqinor-demo-full'

    def setUp(self):
        call_command('seed_demo_company', verbosity=0)
        self.company = Company.objects.get(slug=self.SLUG)

    def test_tickets_span_four_plus_statuses(self):
        from apps.sav.models import Ticket
        statuts = set(Ticket.objects.filter(company=self.company)
                      .values_list('statut', flat=True))
        self.assertGreaterEqual(len(statuts), 4)

    def test_active_maintenance_contracts(self):
        from apps.sav.models import ContratMaintenance
        self.assertGreaterEqual(
            ContratMaintenance.objects.filter(
                company=self.company, actif=True).count(), 3)

    def test_stock_movements_span_six_plus_months(self):
        from apps.stock.models import MouvementStock
        months = {(m.date.year, m.date.month) for m in
                  MouvementStock.objects.filter(company=self.company)}
        self.assertGreaterEqual(len(months), 6)

    def test_some_pieces_consumed(self):
        from apps.sav.models import PieceConsommee
        self.assertTrue(
            PieceConsommee.objects.filter(company=self.company).exists())
