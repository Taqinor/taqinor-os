"""Tests YHARD4 — variantes localisées (titre_localise/corps_localise) sur
ClauseSerializer. Additif : repli FR par défaut inchangé ; ``?locale=``
retourne la traduction stockée dans ``core.ContentTranslation`` quand elle
existe."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.contrats.models import Clause
from core import i18n_content

User = get_user_model()

BASE_CLAUSES = "/api/django/contrats/clauses/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="responsable"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


class ClauseLocalizationTests(TestCase):
    def setUp(self):
        self.company = make_company("yhard4-clause-co", "YHARD4 Clause Co")
        self.user = make_user(self.company, "yhard4_clause_user")
        self.clause = Clause.objects.create(
            company=self.company, titre="Clause garantie",
            corps="Garantie standard de 24 mois.", type_clause="garantie")

    def test_default_response_unaffected(self):
        resp = auth(self.user).get(BASE_CLAUSES)
        row = next(r for r in resp.data["results"] if r["id"] == self.clause.id)
        self.assertEqual(row["titre"], "Clause garantie")
        self.assertEqual(row["titre_localise"], "Clause garantie")

    def test_locale_query_param_returns_translation(self):
        i18n_content.set_translation(
            self.clause, "titre", "ar", "بند الضمان")
        resp = auth(self.user).get(BASE_CLAUSES + "?locale=ar")
        row = next(r for r in resp.data["results"] if r["id"] == self.clause.id)
        self.assertEqual(row["titre_localise"], "بند الضمان")
        self.assertEqual(row["titre"], "Clause garantie")
