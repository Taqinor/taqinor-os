"""Tests CONTRAT32 — Indexation / révision de prix.

Couvre :
- ``calculer_prix_indexe`` : formule part-fixe / révisable, déclaratif.
- ``appliquer_indexation`` : crée un AVENANT ajustant ``Contrat.montant`` du delta,
  trace la date de révision, ne touche jamais ``Contrat.statut`` ; delta nul → pas
  d'avenant.
- Sélecteur scopé société.
- API : CRUD, validation des bornes, actions simuler/appliquer, scope/rôle.
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
from apps.contrats.models import Avenant, Contrat, IndexationPrix

User = get_user_model()

INDEX = "/api/django/contrats/indexations/"


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
        company=company, objet="Contrat PPA", montant=Decimal(montant),
        type_contrat="ppa", statut="actif",
        date_debut=timezone.localdate() - timedelta(days=10))


class IndexationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("idx-svc", "IdxSvc")
        self.user = make_user(self.co, "idx-svc-admin", role="admin")
        self.contrat = make_contrat(self.co, montant="100000")

    def test_calcul_proportion_pure(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0"))
        res = services.calculer_prix_indexe(idx, valeur_actuelle=Decimal("110"))
        # 100000 × 110/100 = 110000.
        self.assertEqual(res["prix_revise"], Decimal("110000.00"))
        self.assertEqual(res["delta"], Decimal("10000.00"))

    def test_calcul_avec_part_fixe(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0.5"))
        # 100000 × (0.5 + 0.5 × 110/100) = 100000 × 1.05 = 105000.
        res = services.calculer_prix_indexe(idx, valeur_actuelle=Decimal("110"))
        self.assertEqual(res["prix_revise"], Decimal("105000.00"))

    def test_appliquer_cree_avenant(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0"))
        res = services.appliquer_indexation(
            idx, valeur_actuelle=Decimal("110"), auteur=self.user)
        self.assertIsNotNone(res["avenant"])
        self.assertEqual(res["delta"], Decimal("10000.00"))
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal("110000.00"))
        self.assertEqual(self.contrat.statut, "actif")  # statut inchangé
        idx.refresh_from_db()
        self.assertEqual(idx.date_derniere_revision, timezone.localdate())
        self.assertEqual(Avenant.objects.filter(contrat=self.contrat).count(), 1)

    def test_appliquer_delta_nul_pas_avenant(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0"))
        res = services.appliquer_indexation(
            idx, valeur_actuelle=Decimal("100"), auteur=self.user)
        self.assertIsNone(res["avenant"])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal("100000"))
        # La date de révision est tout de même tracée.
        idx.refresh_from_db()
        self.assertEqual(idx.date_derniere_revision, timezone.localdate())


class IndexationSelectorTests(TestCase):
    def test_scope_societe(self):
        co = make_company("idx-sel", "IdxSel")
        contrat = make_contrat(co)
        autre_co = make_company("idx-sel-2", "IdxSel2")
        autre = make_contrat(autre_co)
        IndexationPrix.objects.create(
            company=co, contrat=contrat, indice="A", valeur_base=Decimal("1"))
        IndexationPrix.objects.create(
            company=autre_co, contrat=autre, indice="B",
            valeur_base=Decimal("1"))
        self.assertEqual(selectors.indexations_contrat(contrat).count(), 1)


class IndexationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("idx-api", "IdxApi")
        self.admin = make_user(self.co, "idx-api-admin", role="admin")
        self.contrat = make_contrat(self.co, montant="100000")

    def test_creer_company_serveur(self):
        api = auth(self.admin)
        res = api.post(
            INDEX,
            {"contrat": self.contrat.id, "indice": "BTP",
             "valeur_base": "100", "part_fixe": "0", "company": 999},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        idx = IndexationPrix.objects.get(id=res.data["id"])
        self.assertEqual(idx.company_id, self.co.id)  # pas 999

    def test_validation_valeur_base_nulle_400(self):
        api = auth(self.admin)
        res = api.post(
            INDEX,
            {"contrat": self.contrat.id, "indice": "BTP",
             "valeur_base": "0"},
            format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_action_simuler(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0"))
        api = auth(self.admin)
        res = api.post(
            f"{INDEX}{idx.id}/simuler/", {"valeur_actuelle": "120"},
            format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["prix_revise"], "120000.00")

    def test_action_appliquer(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0"))
        api = auth(self.admin)
        res = api.post(
            f"{INDEX}{idx.id}/appliquer/", {"valeur_actuelle": "120"},
            format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIsNotNone(res.data["avenant_id"])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal("120000.00"))

    def test_role_gate(self):
        commercial = make_user(self.co, "idx-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(INDEX).status_code, 403)
