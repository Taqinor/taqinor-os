"""Tests CONTRAT29 — Registre des cautions/garanties liées.

Couvre :
- CRUD du registre, ``company`` posée côté serveur (jamais du corps).
- Filtres par contrat / statut / type.
- Sélecteur scopé société.
- Scope société + rôle sur l'endpoint.
- Le statut de caution n'impacte jamais le statut du contrat.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.models import Caution, Contrat

User = get_user_model()

CAUTIONS = "/api/django/contrats/cautions/"


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


def make_contrat(company):
    return Contrat.objects.create(
        company=company, objet="Marché public", montant=Decimal("500000"),
        type_contrat="vente", statut="actif",
        date_debut=timezone.localdate() - timedelta(days=10))


class CautionSelectorTests(TestCase):
    def test_scope_societe(self):
        co = make_company("caut-sel", "CautSel")
        contrat = make_contrat(co)
        autre_co = make_company("caut-sel-2", "CautSel2")
        autre = make_contrat(autre_co)
        Caution.objects.create(company=co, contrat=contrat)
        Caution.objects.create(company=autre_co, contrat=autre)
        self.assertEqual(selectors.cautions_contrat(contrat).count(), 1)


class CautionApiTests(TestCase):
    def setUp(self):
        self.co = make_company("caut-api", "CautApi")
        self.admin = make_user(self.co, "caut-api-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_creer_company_cote_serveur(self):
        api = auth(self.admin)
        res = api.post(
            CAUTIONS,
            {"contrat": self.contrat.id, "type_caution": "bonne_execution",
             "garant": "Banque XYZ", "reference": "BG-2026-001",
             "montant": "50000", "company": 999},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        c = Caution.objects.get(id=res.data["id"])
        self.assertEqual(c.company_id, self.co.id)  # pas 999
        self.assertEqual(c.garant, "Banque XYZ")
        # Le statut du contrat n'a pas bougé.
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "actif")

    def test_filtre_par_statut_et_type(self):
        Caution.objects.create(
            company=self.co, contrat=self.contrat,
            type_caution="soumission", statut="mainlevee")
        Caution.objects.create(
            company=self.co, contrat=self.contrat,
            type_caution="bonne_execution", statut="active")
        api = auth(self.admin)
        res = api.get(f"{CAUTIONS}?statut=active")
        self.assertEqual(res.data["count"], 1)
        res2 = api.get(f"{CAUTIONS}?type_caution=soumission")
        self.assertEqual(res2.data["count"], 1)

    def test_update_statut_registre(self):
        c = Caution.objects.create(
            company=self.co, contrat=self.contrat, statut="active")
        api = auth(self.admin)
        res = api.patch(
            f"{CAUTIONS}{c.id}/", {"statut": "mainlevee"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        c.refresh_from_db()
        self.assertEqual(c.statut, "mainlevee")

    def test_scope_societe_endpoint(self):
        Caution.objects.create(company=self.co, contrat=self.contrat)
        autre_co = make_company("caut-api-2", "CautApi2")
        autre_admin = make_user(autre_co, "caut-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(f"{CAUTIONS}?contrat={self.contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)

    def test_role_gate(self):
        commercial = make_user(self.co, "caut-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(CAUTIONS).status_code, 403)

    def test_caution_autre_societe_refuse(self):
        autre_co = make_company("caut-api-3", "CautApi3")
        autre = make_contrat(autre_co)
        api = auth(self.admin)
        res = api.post(
            CAUTIONS, {"contrat": autre.id, "montant": "1000"}, format="json")
        self.assertEqual(res.status_code, 400, res.content)
