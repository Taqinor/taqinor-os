"""Tests QHSE3 — commande de seed des ITP solaires (seed_itp_solaire).

Couvre : création des plans + points pour une société, idempotence stricte
(re-jouer ne crée rien et n'écrase aucun champ édité), pose des points d'arrêt
aux bons points (Raccordement & Mise en service), scope société (chaque ligne
porte la bonne société et un --company ne touche que celle-là).
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import PlanInspectionModele, PointControleModele
from apps.qhse.management.commands.seed_itp_solaire import ITP_PLANS

EXPECTED_PLANS = len(ITP_PLANS)
EXPECTED_POINTS = sum(len(p['points']) for p in ITP_PLANS)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def run(**kwargs):
    out = StringIO()
    call_command('seed_itp_solaire', stdout=out, **kwargs)
    return out.getvalue()


class SeedItpSolaireTests(TestCase):
    def setUp(self):
        self.co_a = make_company('seed-itp-a', 'A')
        self.co_b = make_company('seed-itp-b', 'B')

    def test_seeds_plans_and_points_for_a_company(self):
        run(company='seed-itp-a')
        plans = PlanInspectionModele.objects.filter(company=self.co_a)
        points = PointControleModele.objects.filter(company=self.co_a)
        self.assertEqual(plans.count(), EXPECTED_PLANS)
        self.assertEqual(points.count(), EXPECTED_POINTS)
        # Every seeded point belongs to a plan of the same company.
        self.assertTrue(all(pt.plan.company_id == self.co_a.id
                            for pt in points))

    def test_idempotent_rerun_creates_nothing(self):
        run(company='seed-itp-a')
        plans_before = PlanInspectionModele.objects.count()
        points_before = PointControleModele.objects.count()
        run(company='seed-itp-a')  # second run
        self.assertEqual(PlanInspectionModele.objects.count(), plans_before)
        self.assertEqual(PointControleModele.objects.count(), points_before)

    def test_idempotent_rerun_does_not_overwrite_edited_rows(self):
        run(company='seed-itp-a')
        pt = (PointControleModele.objects
              .filter(company=self.co_a).order_by('plan', 'ordre').first())
        pt.intitule = 'Intitulé édité par le fondateur'
        pt.hold_point = not pt.hold_point
        pt.save()
        run(company='seed-itp-a')  # re-run must not clobber the edit
        pt.refresh_from_db()
        self.assertEqual(pt.intitule, 'Intitulé édité par le fondateur')

    def test_hold_points_on_raccordement_and_mise_en_service(self):
        run(company='seed-itp-a')
        for plan in PlanInspectionModele.objects.filter(company=self.co_a):
            holds = {pt.phase for pt in plan.points.filter(hold_point=True)}
            self.assertEqual(holds, {'Raccordement', 'Mise en service'})
            # Non-hold phases must NOT be flagged as hold-points.
            self.assertFalse(
                plan.points.filter(hold_point=True)
                .exclude(phase__in=['Raccordement', 'Mise en service'])
                .exists())

    def test_all_companies_seeded_when_no_arg(self):
        run()  # no --company → every company
        self.assertEqual(
            PlanInspectionModele.objects.filter(company=self.co_a).count(),
            EXPECTED_PLANS)
        self.assertEqual(
            PlanInspectionModele.objects.filter(company=self.co_b).count(),
            EXPECTED_PLANS)

    def test_company_arg_scopes_to_one_company(self):
        run(company='seed-itp-a')
        self.assertEqual(
            PlanInspectionModele.objects.filter(company=self.co_a).count(),
            EXPECTED_PLANS)
        # Company B left empty by a scoped run.
        self.assertEqual(
            PlanInspectionModele.objects.filter(company=self.co_b).count(), 0)

    def test_unknown_company_slug_raises(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            run(company='does-not-exist')
