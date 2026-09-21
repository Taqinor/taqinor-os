"""NTCRD32 — cache d'encours quotidien : le job peuple EncoursCache ; les
hooks bloquants continuent de calculer en LIVE (jamais depuis le cache)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import EncoursCache
from apps.credit.tasks import recalculer_encours_pour_societe
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd32-co', nom='NTCRD32 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD32EncoursCacheTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd32_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd32@example.com')
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N32001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('12000'), created_by=self.user)

    def test_cache_populated_by_job(self):
        n = recalculer_encours_pour_societe(self.company)
        self.assertGreaterEqual(n, 1)
        cache = EncoursCache.objects.get(client=self.client_obj)
        self.assertEqual(cache.encours, Decimal('12000'))

    def test_job_is_idempotent(self):
        recalculer_encours_pour_societe(self.company)
        recalculer_encours_pour_societe(self.company)
        self.assertEqual(
            EncoursCache.objects.filter(client=self.client_obj).count(), 1)

    def test_hold_uses_live_not_cache(self):
        from apps.credit.models import LimiteCredit
        from apps.credit.services import verifier_hold_credit
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        # Cache stale (0) posé, puis nouvelle facture non reflétée dans le cache.
        EncoursCache.objects.update_or_create(
            client=self.client_obj,
            defaults={'company': self.company, 'encours': Decimal('0')})
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N32002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('200000'), created_by=self.user)
        # Live encours (212000) dépasse 100000 → refus, malgré cache à 0.
        result = verifier_hold_credit(self.client_obj, Decimal('0'))
        self.assertFalse(result['autorise'])
