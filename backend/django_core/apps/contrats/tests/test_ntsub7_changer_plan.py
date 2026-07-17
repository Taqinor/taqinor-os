"""Tests NTSUB7 — Changement de plan (upgrade/downgrade) avec proration.

Couvre : un upgrade crée un avenant du delta positif + snapshot le nouveau
plan ; un downgrade applique le delta négatif SANS avoir immédiat (prorata
non appliqué) ; un changement différé n'applique pas de prorata immédiat ; un
plan d'une autre société est refusé.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Avenant,
    Contrat,
    PlanAbonnement,
    PlanRecurrent,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy="admin")


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_plan(company, code, prix):
    return PlanAbonnement.objects.create(
        company=company, code=code, nom=f"Plan {code}",
        plan_recurrent=PlanRecurrent.objects.create(
            company=company, nom=f"Cadence {code}",
            unite=PlanRecurrent.Unite.MENSUEL, intervalle=1),
        prix_base=Decimal(prix))


def make_contrat(company, montant):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal(montant),
        type_contrat="om", statut=Contrat.Statut.ACTIF,
        date_debut=datetime.date(2026, 1, 1))


class ChangerPlanServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub7-svc", "Ntsub7Svc")

    def test_upgrade_cree_avenant_positif_et_snapshot(self):
        contrat = make_contrat(self.co, "500")
        plan = make_plan(self.co, "PRO", "800")
        res = services.changer_plan_contrat(
            contrat, plan, type_changement='immediat')
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal("800"))  # 500 + 300
        self.assertEqual(contrat.plan_abonnement_id, plan.id)
        self.assertEqual(contrat.plan_recurrent_id, plan.plan_recurrent_id)
        self.assertEqual(res['avenant'].montant_delta, Decimal("300"))

    def test_downgrade_applique_delta_sans_avoir_immediat(self):
        contrat = make_contrat(self.co, "800")
        plan = make_plan(self.co, "BASIC", "500")
        res = services.changer_plan_contrat(
            contrat, plan, type_changement='immediat')
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal("500"))  # 800 - 300
        self.assertEqual(res['avenant'].montant_delta, Decimal("-300"))
        self.assertIsNone(res['prorata'])  # downgrade → jamais d'avoir immédiat

    def test_changement_differe_pas_de_prorata_immediat(self):
        contrat = make_contrat(self.co, "500")
        plan = make_plan(self.co, "PRO", "800")
        res = services.changer_plan_contrat(
            contrat, plan, type_changement='differe')
        self.assertIsNone(res['prorata'])
        self.assertEqual(Avenant.objects.filter(contrat=contrat).count(), 1)

    def test_plan_autre_societe_refuse(self):
        autre = make_company("ntsub7-autre", "Ntsub7Autre")
        contrat = make_contrat(self.co, "500")
        plan_autre = make_plan(autre, "X", "800")
        with self.assertRaises(services.ChangementPlanError):
            services.changer_plan_contrat(contrat, plan_autre)


class ChangerPlanApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub7-api", "Ntsub7Api")
        self.admin = make_user(self.co, "ntsub7-admin")

    def test_endpoint_change_le_plan(self):
        contrat = make_contrat(self.co, "500")
        plan = make_plan(self.co, "PRO", "800")
        api = auth(self.admin)
        res = api.post(
            f"/api/django/contrats/contrats/{contrat.id}/changer-plan/",
            {"plan_abonnement": plan.id, "type_changement": "immediat"},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        contrat.refresh_from_db()
        self.assertEqual(contrat.plan_abonnement_id, plan.id)

    def test_endpoint_refuse_plan_autre_societe(self):
        autre = make_company("ntsub7-api2", "Ntsub7Api2")
        plan_autre = make_plan(autre, "X", "800")
        contrat = make_contrat(self.co, "500")
        api = auth(self.admin)
        res = api.post(
            f"/api/django/contrats/contrats/{contrat.id}/changer-plan/",
            {"plan_abonnement": plan_autre.id}, format="json")
        self.assertEqual(res.status_code, 400, res.content)
