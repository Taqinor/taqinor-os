"""XSAL6 — Plans de commission par commercial.

Cette tâche construit la partie ventes-owned (modèle + sélecteur de
résolution cross-app). Le câblage dans `apps/reporting/insights.py` (rapport
commissions) et `apps/crm/selectors.py` (atteinte ObjectifCommercial pour les
paliers) touche des apps hors de cette lane (@lane: backend/ventes-commission
mais Files span reporting+crm) — laissé à une lane reporting/crm dédiée.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal6_plan_commission -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import PlanCommission
from apps.ventes.selectors import resoudre_plan_commission
from testkit.factories import CompanyFactory, UserFactory, another_tenant


class TestResoudrePlanCommission(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.meryem = UserFactory(company=self.company)
        self.junior = UserFactory(company=self.company)

    def test_owner_dedicated_plan_resolved(self):
        PlanCommission.objects.create(
            company=self.company, owner=self.meryem,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('3'))
        PlanCommission.objects.create(
            company=self.company, owner=self.junior,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('1.5'))
        plan_meryem = resoudre_plan_commission(self.company, self.meryem)
        plan_junior = resoudre_plan_commission(self.company, self.junior)
        self.assertEqual(plan_meryem.taux_pct, Decimal('3'))
        self.assertEqual(plan_junior.taux_pct, Decimal('1.5'))

    def test_fallback_to_default_company_plan(self):
        defaut = PlanCommission.objects.create(
            company=self.company, owner=None,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('2'))
        resolved = resoudre_plan_commission(self.company, self.junior)
        self.assertEqual(resolved.id, defaut.id)

    def test_no_plan_returns_none(self):
        self.assertIsNone(resoudre_plan_commission(self.company, self.junior))

    def test_inactive_plan_ignored(self):
        PlanCommission.objects.create(
            company=self.company, owner=self.junior, actif=False,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('9'))
        self.assertIsNone(resoudre_plan_commission(self.company, self.junior))

    def test_cross_tenant_plan_not_leaked(self):
        other_company, other_user = another_tenant()
        PlanCommission.objects.create(
            company=other_company, owner=other_user,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('50'))
        self.assertIsNone(resoudre_plan_commission(self.company, self.junior))


class TestTauxEffectifPaliers(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)

    def test_no_palier_returns_base_taux(self):
        plan = PlanCommission.objects.create(
            company=self.company, owner=self.user,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('3'))
        self.assertEqual(plan.taux_effectif(atteinte_pct=150), Decimal('3'))
        self.assertEqual(plan.taux_effectif(atteinte_pct=None), Decimal('3'))

    def test_palier_atteint_accelerates_rate(self):
        plan = PlanCommission.objects.create(
            company=self.company, owner=self.user,
            base=PlanCommission.Base.CA_DEVIS_SIGNE, taux_pct=Decimal('3'),
            paliers=[{'seuil_atteinte_pct': 100, 'taux': 5}])
        self.assertEqual(plan.taux_effectif(atteinte_pct=120), 5)
        self.assertEqual(plan.taux_effectif(atteinte_pct=80), Decimal('3'))

    def test_par_kwc_base_uses_montant_par_kwc(self):
        plan = PlanCommission.objects.create(
            company=self.company, owner=self.user,
            base=PlanCommission.Base.PAR_KWC, montant_par_kwc=Decimal('50'))
        self.assertEqual(plan.taux_effectif(), Decimal('50'))

    def test_marge_interne_base_is_admin_only_flagged(self):
        # La base 'marge_interne' existe (calcul admin-only côté appelant) —
        # ce test documente juste que le choix est accepté par le modèle.
        plan = PlanCommission.objects.create(
            company=self.company, owner=self.user,
            base=PlanCommission.Base.MARGE_INTERNE, taux_pct=Decimal('10'))
        self.assertEqual(plan.base, 'marge_interne')
