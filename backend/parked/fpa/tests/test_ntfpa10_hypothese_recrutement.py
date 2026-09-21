"""NTFPA10 — HypotheseRecrutement : une hypothèse confirmée est « engagée »
(bascule prévu→engagé pour la vue de variance NTFPA16)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import Departement, HypotheseRecrutement


class TestHypotheseRecrutement(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa10-co', defaults={'nom': 'NTFPA10 Co'})
        self.dept = Departement.objects.create(
            company=self.company, code='IT', nom='IT')

    def test_hypothese_non_engagee_par_defaut(self):
        hyp = HypotheseRecrutement.objects.create(
            company=self.company, poste='Dev', departement=self.dept,
            date_effet=date(2027, 3, 1), salaire_brut_estime=Decimal('12000'))
        self.assertFalse(hyp.est_engage)

    def test_confirmation_bascule_en_engage(self):
        hyp = HypotheseRecrutement.objects.create(
            company=self.company, poste='Dev', departement=self.dept,
            date_effet=date(2027, 3, 1), salaire_brut_estime=Decimal('12000'),
            statut=HypotheseRecrutement.Statut.CONFIRME)
        self.assertTrue(hyp.est_engage)
