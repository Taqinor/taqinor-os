"""Tests CONTRAT26 — Obligations (livrables) & jalons d'un contrat.

Couvre :
- ``creer_jalon`` numérote par contrat en max+1 (jamais count()+1), pose la
  société côté serveur et journalise.
- ``marquer_jalon_atteint`` / ``marquer_obligation_faite`` posent statut + date
  côté serveur, sont idempotents et ne touchent jamais ``Contrat.statut``.
- Sélecteurs scopés société.
- API : CRUD obligations + création de jalon via service (numéro côté serveur),
  actions marquer-atteint / marquer-faite, scope société, rôle, et qu'un
  ``numero``/``statut``/``company`` envoyé au corps est ignoré.
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
from apps.contrats.models import Contrat, JalonContrat, Obligation

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"
JALONS = "/api/django/contrats/jalons/"
OBLIGATIONS = "/api/django/contrats/obligations/"


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


def make_contrat(company, statut="actif", objet="Contrat test"):
    return Contrat.objects.create(
        company=company, objet=objet, montant=Decimal("80000"),
        type_contrat="vente", statut=statut,
        date_debut=timezone.localdate() - timedelta(days=30))


# ---------------------------------------------------------------------------
# Service — jalon (numérotation max+1) & obligations
# ---------------------------------------------------------------------------

class JalonObligationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("oblig-svc", "ObligSvc")
        self.user = make_user(self.co, "oblig-svc-admin", role="admin")

    def test_creer_jalon_numerote_max_plus_un(self):
        contrat = make_contrat(self.co)
        j1 = services.creer_jalon(
            contrat, intitule="Mise en service", auteur=self.user)
        j2 = services.creer_jalon(
            contrat, intitule="Réception", auteur=self.user)
        self.assertEqual(j1.numero, 1)
        self.assertEqual(j2.numero, 2)
        self.assertEqual(j1.company_id, self.co.id)

    def test_creer_jalon_max_plus_un_pas_count(self):
        """Après suppression du jalon n°1, le suivant est max+1 (pas count+1)."""
        contrat = make_contrat(self.co)
        services.creer_jalon(contrat, intitule="A", auteur=self.user)
        services.creer_jalon(contrat, intitule="B", auteur=self.user)
        # Supprime le jalon 1 ; le prochain doit être 3 (max=2 → +1), pas 2.
        JalonContrat.objects.filter(contrat=contrat, numero=1).delete()
        j3 = services.creer_jalon(contrat, intitule="C", auteur=self.user)
        self.assertEqual(j3.numero, 3)

    def test_creer_jalon_intitule_requis(self):
        contrat = make_contrat(self.co)
        with self.assertRaises(ValueError):
            services.creer_jalon(contrat, intitule="  ", auteur=self.user)

    def test_marquer_jalon_atteint_pose_statut_date(self):
        contrat = make_contrat(self.co)
        jalon = services.creer_jalon(contrat, intitule="X", auteur=self.user)
        services.marquer_jalon_atteint(jalon, auteur=self.user)
        jalon.refresh_from_db()
        self.assertEqual(jalon.statut, JalonContrat.Statut.ATTEINT)
        self.assertEqual(jalon.date_atteinte, timezone.localdate())
        # Le statut du contrat n'a pas bougé.
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, "actif")

    def test_marquer_jalon_atteint_idempotent(self):
        contrat = make_contrat(self.co)
        jalon = services.creer_jalon(contrat, intitule="X", auteur=self.user)
        services.marquer_jalon_atteint(jalon, auteur=self.user)
        date1 = jalon.date_atteinte
        services.marquer_jalon_atteint(
            jalon, today=timezone.localdate() + timedelta(days=5),
            auteur=self.user)
        jalon.refresh_from_db()
        self.assertEqual(jalon.date_atteinte, date1)

    def test_marquer_obligation_faite(self):
        contrat = make_contrat(self.co)
        oblig = Obligation.objects.create(
            company=self.co, contrat=contrat, intitule="Livrer le dossier")
        services.marquer_obligation_faite(oblig, auteur=self.user)
        oblig.refresh_from_db()
        self.assertEqual(oblig.statut, Obligation.Statut.FAITE)
        self.assertEqual(oblig.date_realisation, timezone.localdate())
        # Ne touche jamais le statut du contrat.
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, "actif")

    def test_marquer_obligation_faite_idempotent(self):
        contrat = make_contrat(self.co)
        oblig = Obligation.objects.create(
            company=self.co, contrat=contrat, intitule="X")
        services.marquer_obligation_faite(oblig, auteur=self.user)
        d1 = oblig.date_realisation
        services.marquer_obligation_faite(
            oblig, today=timezone.localdate() + timedelta(days=3),
            auteur=self.user)
        oblig.refresh_from_db()
        self.assertEqual(oblig.date_realisation, d1)


# ---------------------------------------------------------------------------
# Sélecteurs — scope société
# ---------------------------------------------------------------------------

class JalonObligationSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("oblig-sel", "ObligSel")
        self.user = make_user(self.co, "oblig-sel-admin", role="admin")

    def test_scope_societe(self):
        contrat = make_contrat(self.co)
        autre_co = make_company("oblig-sel-2", "ObligSel2")
        autre = make_contrat(autre_co)
        services.creer_jalon(contrat, intitule="A", auteur=self.user)
        services.creer_jalon(autre, intitule="B")
        Obligation.objects.create(
            company=self.co, contrat=contrat, intitule="O1")
        Obligation.objects.create(
            company=autre_co, contrat=autre, intitule="O2")
        self.assertEqual(selectors.jalons_contrat(contrat).count(), 1)
        self.assertEqual(selectors.obligations_contrat(contrat).count(), 1)


# ---------------------------------------------------------------------------
# API — création / actions / scope / rôle
# ---------------------------------------------------------------------------

class JalonObligationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("oblig-api", "ObligApi")
        self.admin = make_user(self.co, "oblig-api-admin", role="admin")

    def test_creer_jalon_via_api_numero_cote_serveur(self):
        contrat = make_contrat(self.co)
        api = auth(self.admin)
        res = api.post(
            JALONS,
            {"contrat": contrat.id, "intitule": "Mise en service",
             "numero": 99, "statut": "atteint", "company": 12345},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["numero"], 1)  # pas 99
        self.assertEqual(res.data["statut"], "a_venir")  # pas atteint
        jalon = JalonContrat.objects.get(id=res.data["id"])
        self.assertEqual(jalon.company_id, self.co.id)  # pas 12345

    def test_marquer_atteint_endpoint(self):
        contrat = make_contrat(self.co)
        jalon = services.creer_jalon(contrat, intitule="X", auteur=self.admin)
        api = auth(self.admin)
        res = api.post(f"{JALONS}{jalon.id}/marquer-atteint/", {}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["statut"], "atteint")
        self.assertIsNotNone(res.data["date_atteinte"])

    def test_obligation_crud_et_marquer_faite(self):
        contrat = make_contrat(self.co)
        api = auth(self.admin)
        res = api.post(
            OBLIGATIONS,
            {"contrat": contrat.id, "intitule": "Remise dossier ONEE",
             "redevable": "prestataire", "company": 12345,
             "statut": "faite"},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        # statut writable au POST direct mais date_realisation reste serveur.
        oblig_id = res.data["id"]
        oblig = Obligation.objects.get(id=oblig_id)
        self.assertEqual(oblig.company_id, self.co.id)  # pas 12345
        # marquer-faite pose la date côté serveur.
        res2 = api.post(
            f"{OBLIGATIONS}{oblig_id}/marquer-faite/", {}, format="json")
        self.assertEqual(res2.status_code, 200, res2.content)
        self.assertEqual(res2.data["statut"], "faite")
        self.assertIsNotNone(res2.data["date_realisation"])

    def test_scope_societe_endpoint(self):
        contrat = make_contrat(self.co)
        services.creer_jalon(contrat, intitule="X", auteur=self.admin)
        autre_co = make_company("oblig-api-2", "ObligApi2")
        autre_admin = make_user(autre_co, "oblig-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(f"{JALONS}?contrat={contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)

    def test_role_gate_refuse_non_privilegie(self):
        commercial = make_user(self.co, "oblig-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(JALONS).status_code, 403)
        self.assertEqual(api.get(OBLIGATIONS).status_code, 403)

    def test_jalon_autre_societe_refuse_au_serializer(self):
        autre_co = make_company("oblig-api-3", "ObligApi3")
        autre = make_contrat(autre_co)
        api = auth(self.admin)
        res = api.post(
            JALONS, {"contrat": autre.id, "intitule": "X"}, format="json")
        self.assertEqual(res.status_code, 400, res.content)
