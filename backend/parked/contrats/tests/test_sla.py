"""Tests CONTRAT27 — SLA & pénalités (taux SLA, valeur pénalité).

Couvre :
- ``EngagementSLA.calculer_penalite`` : mode fixe / pourcentage / plafond.
- ``services.calculer_penalite_sla`` : aucune pénalité quand le taux réalisé
  atteint la cible ; pénalité barème sinon ; purement déclaratif (aucune
  écriture, aucun changement de statut).
- Sélecteur scopé société.
- API : CRUD SLA + action ``penalite``, scope société, rôle, ``company`` du corps
  ignoré, validation des bornes.
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
from apps.contrats.models import Contrat, EngagementSLA

User = get_user_model()

SLA = "/api/django/contrats/sla/"


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


def make_contrat(company, montant="100000"):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal(montant),
        type_contrat="om", statut="actif",
        date_debut=timezone.localdate() - timedelta(days=10))


# ---------------------------------------------------------------------------
# Modèle / service — calcul de pénalité
# ---------------------------------------------------------------------------

class PenaliteSLATests(TestCase):
    def setUp(self):
        self.co = make_company("sla-svc", "SlaSvc")
        self.contrat = make_contrat(self.co, montant="100000")

    def test_penalite_fixe(self):
        sla = EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="Dispo 98%",
            taux_cible=Decimal("98"), mode_penalite="fixe",
            valeur_penalite=Decimal("2500"))
        self.assertEqual(sla.calculer_penalite(), Decimal("2500.00"))

    def test_penalite_pourcentage(self):
        sla = EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="PR 80%",
            taux_cible=Decimal("80"), mode_penalite="pourcentage",
            valeur_penalite=Decimal("5"))
        # 5 % de 100000 = 5000.
        self.assertEqual(sla.calculer_penalite(), Decimal("5000.00"))

    def test_penalite_plafonnee(self):
        sla = EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="X",
            mode_penalite="pourcentage", valeur_penalite=Decimal("50"),
            penalite_max=Decimal("3000"))
        # 50 % de 100000 = 50000, plafonné à 3000.
        self.assertEqual(sla.calculer_penalite(), Decimal("3000.00"))

    def test_aucune_penalite_si_cible_atteinte(self):
        sla = EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="Dispo",
            taux_cible=Decimal("98"), mode_penalite="fixe",
            valeur_penalite=Decimal("2500"))
        res = services.calculer_penalite_sla(sla, taux_realise=Decimal("99"))
        self.assertEqual(res["penalite"], Decimal("0.00"))
        self.assertTrue(res["respecte"])

    def test_penalite_due_si_cible_manquee(self):
        sla = EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="Dispo",
            taux_cible=Decimal("98"), mode_penalite="fixe",
            valeur_penalite=Decimal("2500"))
        res = services.calculer_penalite_sla(sla, taux_realise=Decimal("95"))
        self.assertEqual(res["penalite"], Decimal("2500.00"))
        self.assertFalse(res["respecte"])

    def test_service_ne_cree_aucune_ecriture(self):
        sla = EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="Dispo",
            taux_cible=Decimal("98"), valeur_penalite=Decimal("1000"))
        avant = self.contrat.activites.count()
        services.calculer_penalite_sla(sla, taux_realise=Decimal("90"))
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "actif")
        self.assertEqual(self.contrat.activites.count(), avant)


# ---------------------------------------------------------------------------
# Sélecteur — scope société
# ---------------------------------------------------------------------------

class SLASelectorTests(TestCase):
    def test_scope_societe(self):
        co = make_company("sla-sel", "SlaSel")
        contrat = make_contrat(co)
        autre_co = make_company("sla-sel-2", "SlaSel2")
        autre = make_contrat(autre_co)
        EngagementSLA.objects.create(
            company=co, contrat=contrat, libelle="A")
        EngagementSLA.objects.create(
            company=autre_co, contrat=autre, libelle="B")
        self.assertEqual(
            selectors.engagements_sla_contrat(contrat).count(), 1)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class SLAApiTests(TestCase):
    def setUp(self):
        self.co = make_company("sla-api", "SlaApi")
        self.admin = make_user(self.co, "sla-api-admin", role="admin")
        self.contrat = make_contrat(self.co, montant="100000")

    def test_creer_sla_company_cote_serveur(self):
        api = auth(self.admin)
        res = api.post(
            SLA,
            {"contrat": self.contrat.id, "libelle": "Dispo 98%",
             "taux_cible": "98", "mode_penalite": "fixe",
             "valeur_penalite": "2500", "company": 999},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        sla = EngagementSLA.objects.get(id=res.data["id"])
        self.assertEqual(sla.company_id, self.co.id)  # pas 999

    def test_validation_taux_hors_bornes_400(self):
        api = auth(self.admin)
        res = api.post(
            SLA,
            {"contrat": self.contrat.id, "libelle": "X", "taux_cible": "150"},
            format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_action_penalite(self):
        sla = EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="Dispo",
            taux_cible=Decimal("98"), mode_penalite="pourcentage",
            valeur_penalite=Decimal("5"))
        api = auth(self.admin)
        res = api.post(
            f"{SLA}{sla.id}/penalite/", {"taux_realise": "90"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["penalite"], "5000.00")
        self.assertFalse(res.data["respecte"])

    def test_scope_societe_endpoint(self):
        EngagementSLA.objects.create(
            company=self.co, contrat=self.contrat, libelle="A")
        autre_co = make_company("sla-api-2", "SlaApi2")
        autre_admin = make_user(autre_co, "sla-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(f"{SLA}?contrat={self.contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)

    def test_role_gate(self):
        commercial = make_user(self.co, "sla-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(SLA).status_code, 403)
