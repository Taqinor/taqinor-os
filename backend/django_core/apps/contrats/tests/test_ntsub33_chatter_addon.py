"""Tests NTSUB33 — journalisation ContratActivity sur ajout/retrait d'add-on."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import (
    AbonnementAddOnLigne,
    AddOnAbonnement,
    Contrat,
    ContratActivity,
)

User = get_user_model()

LIGNES = "/api/django/contrats/addon-lignes/"


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


class ChatterAddonTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub33", "Ntsub33")
        self.admin = make_user(self.co, "ntsub33-admin")
        self.contrat = Contrat.objects.create(
            company=self.co, objet="Contrat", montant=Decimal("500"),
            type_contrat="om", statut=Contrat.Statut.ACTIF)
        self.addon = AddOnAbonnement.objects.create(
            company=self.co, code="SUP", nom="Supervision",
            prix_unitaire=Decimal("150"))

    def test_ajout_addon_journalise(self):
        api = auth(self.admin)
        res = api.post(LIGNES, {
            "type_cible": "contrat", "cible_id": self.contrat.id,
            "addon": self.addon.id, "quantite": 1,
            "actif_depuis": "2026-01-01"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        entry = ContratActivity.objects.filter(
            contrat=self.contrat, field='addon').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.new_value, 'SUP')
        self.assertEqual(entry.auteur_id, self.admin.id)

    def test_retrait_addon_journalise(self):
        ligne = AbonnementAddOnLigne.objects.create(
            company=self.co,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=self.contrat.id, addon=self.addon, quantite=1,
            actif_depuis=datetime.date(2026, 1, 1))
        api = auth(self.admin)
        res = api.delete(f"{LIGNES}{ligne.id}/")
        self.assertEqual(res.status_code, 204, res.content)
        entry = ContratActivity.objects.filter(
            contrat=self.contrat, field='addon', old_value='SUP').first()
        self.assertIsNotNone(entry)
