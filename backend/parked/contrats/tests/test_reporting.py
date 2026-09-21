"""Tests CONTRAT35 — Reporting valeur contractuelle & taux de renouvellement.

Couvre :
- ``reporting_contrats`` : valeur totale/active, valeur par type, nombre de
  renouvellements, contrats renouvelés, contrats échus, taux de renouvellement.
- Scope société + rôle sur l'endpoint.
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
from apps.contrats.models import Contrat

User = get_user_model()

REPORTING = "/api/django/contrats/contrats/reporting/"


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


def make_contrat(company, statut="actif", montant="50000", type_contrat="vente",
                 date_fin=None, nb_renouvellements=0):
    return Contrat.objects.create(
        company=company, objet="C", montant=Decimal(montant),
        type_contrat=type_contrat, statut=statut,
        date_debut=timezone.localdate() - timedelta(days=400),
        date_fin=date_fin, nb_renouvellements=nb_renouvellements)


class ReportingSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("rep-svc", "RepSvc")

    def test_valeurs(self):
        make_contrat(self.co, statut="actif", montant="10000",
                     type_contrat="vente")
        make_contrat(self.co, statut="actif", montant="20000",
                     type_contrat="om")
        make_contrat(self.co, statut="brouillon", montant="5000",
                     type_contrat="vente")
        data = selectors.reporting_contrats(self.co)
        self.assertEqual(data["valeur_totale"], Decimal("35000"))
        self.assertEqual(data["valeur_active"], Decimal("30000"))
        self.assertEqual(data["valeur_par_type"]["vente"], Decimal("15000"))
        self.assertEqual(data["valeur_par_type"]["om"], Decimal("20000"))

    def test_taux_renouvellement(self):
        passe = timezone.localdate() - timedelta(days=10)
        # 2 contrats échus (date_fin passée), 1 renouvelé.
        make_contrat(self.co, statut="actif", date_fin=passe,
                     nb_renouvellements=2)
        make_contrat(self.co, statut="expire", date_fin=passe,
                     nb_renouvellements=0)
        # 1 contrat actif non échu (date future) : hors base.
        make_contrat(
            self.co, statut="actif",
            date_fin=timezone.localdate() + timedelta(days=200))
        data = selectors.reporting_contrats(self.co)
        self.assertEqual(data["nb_echus"], 2)
        self.assertEqual(data["nb_contrats_renouveles"], 1)
        self.assertEqual(data["nb_renouvellements"], 2)
        # 1 renouvelé / 2 échus = 50 %.
        self.assertEqual(data["taux_renouvellement"], Decimal("50.00"))

    def test_taux_zero_si_aucun_echu(self):
        make_contrat(
            self.co, statut="actif",
            date_fin=timezone.localdate() + timedelta(days=200))
        data = selectors.reporting_contrats(self.co)
        self.assertEqual(data["nb_echus"], 0)
        self.assertEqual(data["taux_renouvellement"], Decimal("0.00"))


class ReportingApiTests(TestCase):
    def setUp(self):
        self.co = make_company("rep-api", "RepApi")
        self.admin = make_user(self.co, "rep-api-admin", role="admin")

    def test_endpoint(self):
        make_contrat(self.co, statut="actif", montant="10000")
        api = auth(self.admin)
        res = api.get(REPORTING)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["valeur_active"], "10000.00")
        self.assertIn("taux_renouvellement", res.data)

    def test_scope_societe(self):
        make_contrat(self.co, statut="actif", montant="10000")
        autre_co = make_company("rep-api-2", "RepApi2")
        make_contrat(autre_co, statut="actif", montant="99999")
        autre_admin = make_user(autre_co, "rep-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(REPORTING)
        self.assertEqual(res.data["valeur_active"], "99999.00")

    def test_role_gate(self):
        commercial = make_user(self.co, "rep-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(REPORTING).status_code, 403)
