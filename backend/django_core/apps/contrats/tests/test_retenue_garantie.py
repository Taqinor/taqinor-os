"""Tests CONTRAT28 — Retenue de garantie (suivi de libération).

Couvre :
- ``montant_retenu`` calculé côté serveur (= base × taux %).
- ``services.liberer_retenue`` : statut + date côté serveur, idempotent, refus de
  libérer une retenue annulée, ne touche jamais ``Contrat.statut``.
- Sélecteur scopé société.
- API : création (montant calculé serveur), action liberer, scope société, rôle,
  ``company``/``montant_retenu``/``statut`` du corps ignorés.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import Contrat, RetenueGarantie

User = get_user_model()

RETENUES = "/api/django/contrats/retenues-garantie/"


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
        company=company, objet="Marché EPC", montant=Decimal("500000"),
        type_contrat="vente", statut="actif",
        date_debut=timezone.localdate() - timedelta(days=10))


class RetenueServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("retg-svc", "RetgSvc")
        self.user = make_user(self.co, "retg-svc-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_calcul_montant_retenu(self):
        r = RetenueGarantie(
            montant_base=Decimal("200000"), taux=Decimal("5"))
        self.assertEqual(r.calculer_montant_retenu(), Decimal("10000.00"))

    def test_liberer_pose_statut_date(self):
        r = RetenueGarantie.objects.create(
            company=self.co, contrat=self.contrat,
            montant_base=Decimal("100000"), taux=Decimal("5"),
            montant_retenu=Decimal("5000"))
        services.liberer_retenue(r, auteur=self.user)
        r.refresh_from_db()
        self.assertEqual(r.statut, RetenueGarantie.Statut.LIBEREE)
        self.assertEqual(r.date_liberation_effective, timezone.localdate())
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "actif")

    def test_liberer_idempotent(self):
        r = RetenueGarantie.objects.create(
            company=self.co, contrat=self.contrat,
            montant_base=Decimal("100000"), taux=Decimal("5"))
        services.liberer_retenue(r, auteur=self.user)
        d1 = r.date_liberation_effective
        services.liberer_retenue(
            r, today=timezone.localdate() + timedelta(days=5),
            auteur=self.user)
        r.refresh_from_db()
        self.assertEqual(r.date_liberation_effective, d1)

    def test_liberer_annulee_refuse(self):
        r = RetenueGarantie.objects.create(
            company=self.co, contrat=self.contrat,
            statut=RetenueGarantie.Statut.ANNULEE)
        with self.assertRaises(ValueError):
            services.liberer_retenue(r, auteur=self.user)


class RetenueSelectorTests(TestCase):
    def test_scope_societe(self):
        co = make_company("retg-sel", "RetgSel")
        contrat = make_contrat(co)
        autre_co = make_company("retg-sel-2", "RetgSel2")
        autre = make_contrat(autre_co)
        RetenueGarantie.objects.create(company=co, contrat=contrat)
        RetenueGarantie.objects.create(company=autre_co, contrat=autre)
        self.assertEqual(
            selectors.retenues_garantie_contrat(contrat).count(), 1)


class RetenueApiTests(TestCase):
    def setUp(self):
        self.co = make_company("retg-api", "RetgApi")
        self.admin = make_user(self.co, "retg-api-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_creer_montant_calcule_serveur(self):
        api = auth(self.admin)
        res = api.post(
            RETENUES,
            {"contrat": self.contrat.id, "montant_base": "200000",
             "taux": "5", "montant_retenu": "999999",
             "statut": "liberee", "company": 999},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        r = RetenueGarantie.objects.get(id=res.data["id"])
        self.assertEqual(r.montant_retenu, Decimal("10000.00"))  # pas 999999
        self.assertEqual(r.statut, "retenue")  # pas liberee
        self.assertEqual(r.company_id, self.co.id)  # pas 999

    def test_action_liberer(self):
        r = RetenueGarantie.objects.create(
            company=self.co, contrat=self.contrat,
            montant_base=Decimal("100000"), taux=Decimal("5"),
            montant_retenu=Decimal("5000"))
        api = auth(self.admin)
        res = api.post(f"{RETENUES}{r.id}/liberer/", {}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["statut"], "liberee")
        self.assertIsNotNone(res.data["date_liberation_effective"])

    def test_liberer_annulee_400(self):
        r = RetenueGarantie.objects.create(
            company=self.co, contrat=self.contrat,
            statut=RetenueGarantie.Statut.ANNULEE)
        api = auth(self.admin)
        res = api.post(f"{RETENUES}{r.id}/liberer/", {}, format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_scope_societe_endpoint(self):
        RetenueGarantie.objects.create(company=self.co, contrat=self.contrat)
        autre_co = make_company("retg-api-2", "RetgApi2")
        autre_admin = make_user(autre_co, "retg-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(f"{RETENUES}?contrat={self.contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)

    def test_role_gate(self):
        commercial = make_user(self.co, "retg-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(RETENUES).status_code, 403)
