"""NTCRD33 — expiration des dérogations : une dérogation dont valide_jusqu_au
est dépassée passe à 'expiree' et ne lève plus le hold."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import DerogationCredit, LimiteCredit
from apps.credit.services import verifier_hold_credit
from apps.credit.tasks import expirer_derogations
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd33-co', nom='NTCRD33 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD33ExpirerDerogationsTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd33_user', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd33@example.com')
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('1000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)

    def test_expired_derogation_no_longer_lifts_hold(self):
        now = timezone.now()
        d = DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'),
            statut=DerogationCredit.Statut.APPROUVEE,
            demandeur=self.user,
            valide_jusqu_au=now - timedelta(days=1))
        # Avant expiration explicite : est_valide False (déjà dépassée).
        self.assertFalse(d.est_valide)
        # Le job d'expiration passe le statut à 'expiree'.
        n = expirer_derogations(now=now)
        self.assertEqual(n, 1)
        d.refresh_from_db()
        self.assertEqual(d.statut, DerogationCredit.Statut.EXPIREE)
        # Le hold n'est plus levé.
        result = verifier_hold_credit(self.client_obj, Decimal('5000'))
        self.assertFalse(result['autorise'])

    def test_valid_derogation_not_expired(self):
        now = timezone.now()
        DerogationCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_demande=Decimal('5000'),
            statut=DerogationCredit.Statut.APPROUVEE,
            valide_jusqu_au=now + timedelta(days=10))
        self.assertEqual(expirer_derogations(now=now), 0)
