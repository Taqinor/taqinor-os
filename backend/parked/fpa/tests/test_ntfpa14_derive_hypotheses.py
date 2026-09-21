"""NTFPA14 — derive_hypotheses : un écart confirmé vs prévu > 15 % est flagué."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import CycleBudgetaire, Departement, HypotheseRecrutement
from apps.fpa.selectors import derive_hypotheses


class TestDeriveHypotheses(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa14-co', defaults={'nom': 'NTFPA14 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='IT', nom='IT')

    def _hyp(self, montant, statut):
        return HypotheseRecrutement.objects.create(
            company=self.company, poste='Dev', departement=self.dept,
            date_effet=date(2027, 3, 1), salaire_brut_estime=Decimal(montant),
            statut=statut)

    def test_depassement_flague(self):
        # Prévu 10000, confirmé 12000 → écart +20 % > 15 %.
        self._hyp('10000', HypotheseRecrutement.Statut.HYPOTHESE)
        self._hyp('12000', HypotheseRecrutement.Statut.CONFIRME)
        rows = derive_hypotheses(self.company, self.cycle)
        row = next(r for r in rows if r['departement_id'] == self.dept.pk)
        self.assertTrue(row['depasse'])

    def test_ecart_faible_non_flague(self):
        # Prévu 10000, confirmé 10500 → écart +5 % ≤ 15 %.
        self._hyp('10000', HypotheseRecrutement.Statut.HYPOTHESE)
        self._hyp('10500', HypotheseRecrutement.Statut.CONFIRME)
        rows = derive_hypotheses(self.company, self.cycle)
        row = next(r for r in rows if r['departement_id'] == self.dept.pk)
        self.assertFalse(row['depasse'])
