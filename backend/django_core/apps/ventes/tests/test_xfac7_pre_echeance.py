"""
XFAC7 — Rappel de courtoisie pré-échéance (J-N avant échéance).

Une facture à échéance J+5 déclenche exactement UN rappel courtois avec lien
de paiement, jamais deux, désactivable, factures payées/annulées/exclues
ignorées, tests.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac7_pre_echeance -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.parametres.models_company import CompanyProfile
from apps.ventes.models import EmailLog, Facture
from apps.ventes.scheduled import pre_echeance_reminders, casablanca_today

MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac7-co', nom='XFAC7 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac7@example.com'):
    return Client.objects.create(
        company=company, nom='PreEcheance', prenom='Client',
        email=email, telephone='+212600000055', adresse='Casablanca',
    )


class XFAC7PreEcheanceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        # Anchor to the SAME "today" basis the sweep uses (casablanca_today,
        # Africa/Casablanca) — using UTC now().date() here flaked the J-5 window
        # by one day when CI ran between 23:00–24:00 UTC (Casablanca already J+1).
        today = casablanca_today()
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal('5000'),
            date_echeance=today + timedelta(days=5),
        )

    def test_default_n5_triggers_exactly_one_reminder(self):
        sent = pre_echeance_reminders()
        self.assertEqual(sent, 1)
        logs = EmailLog.objects.filter(facture=self.facture)
        self.assertEqual(logs.count(), 1)
        self.assertTrue(logs.first().reference.endswith('::pre_echeance'))

    def test_never_sends_twice(self):
        pre_echeance_reminders()
        sent2 = pre_echeance_reminders()
        self.assertEqual(sent2, 0)
        self.assertEqual(
            EmailLog.objects.filter(facture=self.facture).count(), 1)

    def test_disabled_when_n_is_zero(self):
        profile = CompanyProfile.get(company=self.company)
        profile.rappel_pre_echeance_jours = 0
        profile.save(update_fields=['rappel_pre_echeance_jours'])
        sent = pre_echeance_reminders()
        self.assertEqual(sent, 0)

    def test_paid_facture_ignored(self):
        self.facture.statut = Facture.Statut.PAYEE
        self.facture.save(update_fields=['statut'])
        sent = pre_echeance_reminders()
        self.assertEqual(sent, 0)

    def test_excluded_facture_ignored(self):
        self.facture.exclu_relances = True
        self.facture.save(update_fields=['exclu_relances'])
        sent = pre_echeance_reminders()
        self.assertEqual(sent, 0)

    def test_wrong_delay_window_ignored(self):
        self.facture.date_echeance = timezone.now().date() + timedelta(days=10)
        self.facture.save(update_fields=['date_echeance'])
        sent = pre_echeance_reminders()
        self.assertEqual(sent, 0)

    def test_custom_n_respected(self):
        profile = CompanyProfile.get(company=self.company)
        profile.rappel_pre_echeance_jours = 3
        profile.save(update_fields=['rappel_pre_echeance_jours'])
        # échéance à J+5 ne correspond plus à N=3 → pas de rappel.
        sent = pre_echeance_reminders()
        self.assertEqual(sent, 0)
        self.facture.date_echeance = casablanca_today() + timedelta(days=3)
        self.facture.save(update_fields=['date_echeance'])
        sent = pre_echeance_reminders()
        self.assertEqual(sent, 1)
