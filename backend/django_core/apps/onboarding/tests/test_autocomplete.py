"""NTDMO12 — auto-complétion des items via le bus core.events."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.events import devis_sent, facture_payee
from apps.onboarding.models import OnboardingChecklistItem, OnboardingProgress

User = get_user_model()


class _FakeDevis:
    """Stub porteur des attributs lus par le récepteur (pas un modèle)."""
    def __init__(self, company):
        self.company = company
        self.pk = 1


class _FakeFacture:
    def __init__(self, company, created_by):
        self.company = company
        self.created_by = created_by


class OnboardingAutoCompleteTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co', slug='co-ac')
        self.user = User.objects.create_user(
            'u', password='x', company=self.company)

    def _is_done(self, key):
        item = OnboardingChecklistItem.objects.get(key=key)
        p = OnboardingProgress.objects.filter(
            company=self.company, user=self.user, item=item).first()
        return bool(p and p.complete_le)

    # NB : ``send_robust`` isole le récepteur onboarding — les autres apps
    # (crm/notifications) écoutent aussi ces événements et lisent des attributs
    # (``devis.statut``/``facture.reference``) absents de ces stubs légers ;
    # ``send`` propagerait leur AttributeError alors qu'en prod l'objet réel
    # les porte. Le récepteur onboarding, lui, est déjà best-effort.
    def test_devis_sent_auto_completes_premier_devis(self):
        self.assertFalse(self._is_done('premier_devis'))
        devis_sent.send_robust(
            sender=None, devis=_FakeDevis(self.company), user=self.user,
            ancien_statut='brouillon')
        self.assertTrue(self._is_done('premier_devis'))

    def test_facture_payee_auto_completes_premier_paiement(self):
        facture_payee.send_robust(
            sender=None,
            instance=_FakeFacture(self.company, self.user),
            company=self.company)
        self.assertTrue(self._is_done('premier_paiement'))

    def test_idempotent_no_double_complete(self):
        d = _FakeDevis(self.company)
        devis_sent.send_robust(sender=None, devis=d, user=self.user,
                               ancien_statut='brouillon')
        devis_sent.send_robust(sender=None, devis=d, user=self.user,
                               ancien_statut='brouillon')
        item = OnboardingChecklistItem.objects.get(key='premier_devis')
        self.assertEqual(OnboardingProgress.objects.filter(
            user=self.user, item=item).count(), 1)
