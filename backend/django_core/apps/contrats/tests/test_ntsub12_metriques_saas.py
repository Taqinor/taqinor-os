"""Tests NTSUB12 — Métriques SaaS : ARR bridge, Quick Ratio, Rule of 40."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()

METRIQUES = "/api/django/contrats/contrats/metriques-saas/"


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


def make_contrat_mrr(company, montant_mensuel):
    contrat = Contrat.objects.create(
        company=company, objet="Abo", montant=Decimal(montant_mensuel),
        type_contrat="om", statut=Contrat.Statut.ACTIF,
        date_debut=datetime.date(2026, 1, 1))
    EcheancierContrat.objects.create(
        company=company, contrat=contrat,
        periodicite=EcheancierContrat.Periodicite.MENSUELLE,
        montant_total=Decimal(montant_mensuel),
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
    return contrat


class MetriquesSaasSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub12", "Ntsub12")

    def test_arr_fin_egale_mrr_fois_12(self):
        make_contrat_mrr(self.co, "1000")
        bridge = selectors.arr_bridge(
            self.co, datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
        self.assertEqual(bridge['arr_fin'], Decimal("12000.00"))

    def test_quick_ratio_none_sans_perte(self):
        make_contrat_mrr(self.co, "1000")
        # Fenêtre passée sans contraction/churn → dénominateur 0 → None.
        qr = selectors.quick_ratio(
            self.co, datetime.date(2025, 1, 1), datetime.date(2025, 1, 31))
        self.assertIsNone(qr)

    def test_rule_of_40_structure_et_guard(self):
        make_contrat_mrr(self.co, "1000")
        ro = selectors.rule_of_40(
            self.co, datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
        self.assertIn('croissance_arr_pct', ro)
        self.assertIn('marge_pct', ro)
        self.assertIn('rule_of_40', ro)  # ne lève jamais (div-by-zéro gardée)


class MetriquesSaasApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub12-api", "Ntsub12Api")
        self.admin = make_user(self.co, "ntsub12-admin")

    def test_endpoint_ok(self):
        make_contrat_mrr(self.co, "1000")
        api = auth(self.admin)
        res = api.get(f"{METRIQUES}?debut=2026-01-01&fin=2026-01-31")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['arr_bridge']['arr_fin'], "12000.00")

    def test_endpoint_dates_invalides_400(self):
        api = auth(self.admin)
        res = api.get(f"{METRIQUES}?debut=zzz&fin=2026-01-31")
        self.assertEqual(res.status_code, 400, res.content)
