"""Tests ZCTR1 — Plan de facturation récurrente réutilisable (RecurringPlan).

Couvre :
- CRUD company-scopé de ``PlanRecurrent`` (API), ``company`` posée côté serveur.
- ``mois_par_cycle`` (unite x intervalle).
- ``debut_periode_alignee`` : alignement calendaire trimestriel.
- ``selectors.mois_par_cycle_contrat`` : lit le plan rattaché quand présent,
  sinon retombe sur la périodicité de l'échéancier, sinon ``None`` (absence de
  plan/échéancier = comportement inchangé).
- Validation same-company de ``Contrat.plan_recurrent``.
- Seeder idempotent (3 plans standard, additif, n'écrase jamais un plan
  existant / édité).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.management.commands.seed_plans_recurrents import (
    seed_plans_recurrents_for_company,
)
from apps.contrats.models import Contrat, EcheancierContrat, PlanRecurrent

User = get_user_model()

PLANS = "/api/django/contrats/plans-recurrents/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_contrat(company, montant="1000"):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal(montant),
        type_contrat="om", statut=Contrat.Statut.ACTIF)


class PlanRecurrentModelTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr1-model", "Zctr1Model")

    def test_mois_par_cycle_mensuel(self):
        plan = PlanRecurrent.objects.create(
            company=self.co, nom="Mensuel", unite=PlanRecurrent.Unite.MENSUEL,
            intervalle=1)
        self.assertEqual(plan.mois_par_cycle(), 1)

    def test_mois_par_cycle_trimestriel_intervalle_2(self):
        plan = PlanRecurrent.objects.create(
            company=self.co, nom="Bi-trimestriel",
            unite=PlanRecurrent.Unite.TRIMESTRIEL, intervalle=2)
        self.assertEqual(plan.mois_par_cycle(), 6)

    def test_debut_periode_alignee_trimestriel(self):
        import datetime

        plan = PlanRecurrent.objects.create(
            company=self.co, nom="TrimAligne",
            unite=PlanRecurrent.Unite.TRIMESTRIEL, intervalle=1,
            aligner_debut_periode=True)
        # 15 février → 1er trimestre civil (janvier-mars) → 1er janvier.
        ref = datetime.date(2026, 2, 15)
        self.assertEqual(
            plan.debut_periode_alignee(ref), datetime.date(2026, 1, 1))
        # 20 août → 3e trimestre (juillet-sept) → 1er juillet.
        ref2 = datetime.date(2026, 8, 20)
        self.assertEqual(
            plan.debut_periode_alignee(ref2), datetime.date(2026, 7, 1))

    def test_sans_alignement_renvoie_date_inchangee(self):
        import datetime

        plan = PlanRecurrent.objects.create(
            company=self.co, nom="TrimNonAligne",
            unite=PlanRecurrent.Unite.TRIMESTRIEL, intervalle=1,
            aligner_debut_periode=False)
        ref = datetime.date(2026, 2, 15)
        self.assertEqual(plan.debut_periode_alignee(ref), ref)


class MoisParCycleContratSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr1-sel", "Zctr1Sel")

    def test_lit_le_plan_rattache_actif(self):
        plan = PlanRecurrent.objects.create(
            company=self.co, nom="Trim", unite=PlanRecurrent.Unite.TRIMESTRIEL,
            intervalle=1, actif=True)
        contrat = make_contrat(self.co)
        contrat.plan_recurrent = plan
        contrat.save(update_fields=['plan_recurrent'])
        self.assertEqual(selectors.mois_par_cycle_contrat(contrat), 3)

    def test_plan_inactif_retombe_sur_echeancier(self):
        plan = PlanRecurrent.objects.create(
            company=self.co, nom="TrimInactif",
            unite=PlanRecurrent.Unite.TRIMESTRIEL, intervalle=1, actif=False)
        contrat = make_contrat(self.co)
        contrat.plan_recurrent = plan
        contrat.save(update_fields=['plan_recurrent'])
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE)
        self.assertEqual(selectors.mois_par_cycle_contrat(contrat), 1)

    def test_sans_plan_retombe_sur_echeancier(self):
        contrat = make_contrat(self.co)
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.ANNUELLE)
        self.assertEqual(selectors.mois_par_cycle_contrat(contrat), 12)

    def test_sans_plan_ni_echeancier_renvoie_none(self):
        contrat = make_contrat(self.co)
        self.assertIsNone(selectors.mois_par_cycle_contrat(contrat))


class PlanRecurrentApiTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr1-api", "Zctr1Api")
        self.admin = make_user(self.co, "zctr1-api-admin", role="admin")

    def test_creer_company_posee_serveur(self):
        api = auth(self.admin)
        res = api.post(
            PLANS,
            {"nom": "Semestriel", "unite": "semestriel", "intervalle": 1,
             "company": 999},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        plan = PlanRecurrent.objects.get(id=res.data["id"])
        self.assertEqual(plan.company_id, self.co.id)  # pas 999

    def test_intervalle_zero_refuse(self):
        api = auth(self.admin)
        res = api.post(
            PLANS,
            {"nom": "Invalide", "unite": "mensuel", "intervalle": 0},
            format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_filtre_actif(self):
        PlanRecurrent.objects.create(
            company=self.co, nom="Actif1", actif=True)
        PlanRecurrent.objects.create(
            company=self.co, nom="Inactif1", actif=False)
        api = auth(self.admin)
        res = api.get(f"{PLANS}?actif=1")
        self.assertEqual(res.status_code, 200, res.content)
        noms = {row["nom"] for row in res.data["results"]} if isinstance(
            res.data, dict) and "results" in res.data else {
            row["nom"] for row in res.data}
        self.assertIn("Actif1", noms)
        self.assertNotIn("Inactif1", noms)

    def test_scope_societe(self):
        autre_co = make_company("zctr1-api-2", "Zctr1Api2")
        PlanRecurrent.objects.create(company=self.co, nom="MonPlan")
        PlanRecurrent.objects.create(company=autre_co, nom="AutrePlan")
        api = auth(self.admin)
        res = api.get(PLANS)
        noms = {row["nom"] for row in res.data["results"]} if isinstance(
            res.data, dict) and "results" in res.data else {
            row["nom"] for row in res.data}
        self.assertIn("MonPlan", noms)
        self.assertNotIn("AutrePlan", noms)

    def test_contrat_plan_recurrent_autre_societe_refuse(self):
        autre_co = make_company("zctr1-api-3", "Zctr1Api3")
        plan_autre = PlanRecurrent.objects.create(
            company=autre_co, nom="PlanAutreSociete")
        contrat = make_contrat(self.co)
        api = auth(self.admin)
        res = api.patch(
            f"/api/django/contrats/contrats/{contrat.id}/",
            {"plan_recurrent": plan_autre.id}, format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_contrat_plan_recurrent_meme_societe_accepte(self):
        plan = PlanRecurrent.objects.create(company=self.co, nom="MonPlanOK")
        contrat = make_contrat(self.co)
        api = auth(self.admin)
        res = api.patch(
            f"/api/django/contrats/contrats/{contrat.id}/",
            {"plan_recurrent": plan.id}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        contrat.refresh_from_db()
        self.assertEqual(contrat.plan_recurrent_id, plan.id)


class SeedPlansRecurrentsTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr1-seed", "Zctr1Seed")

    def test_seed_cree_3_plans(self):
        created = seed_plans_recurrents_for_company(self.co)
        self.assertEqual(created, 3)
        self.assertEqual(
            PlanRecurrent.objects.filter(company=self.co).count(), 3)

    def test_seed_idempotent_ne_duplique_pas(self):
        seed_plans_recurrents_for_company(self.co)
        created_second = seed_plans_recurrents_for_company(self.co)
        self.assertEqual(created_second, 0)
        self.assertEqual(
            PlanRecurrent.objects.filter(company=self.co).count(), 3)

    def test_seed_ne_touche_pas_un_plan_edite(self):
        seed_plans_recurrents_for_company(self.co)
        plan = PlanRecurrent.objects.get(company=self.co, nom="Mensuel")
        plan.delai_cloture_auto_jours = 45
        plan.save(update_fields=['delai_cloture_auto_jours'])

        seed_plans_recurrents_for_company(self.co)

        plan.refresh_from_db()
        self.assertEqual(plan.delai_cloture_auto_jours, 45)
