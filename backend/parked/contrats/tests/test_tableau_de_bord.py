"""Tests CONTRAT33 — Tableau de bord contrats (actifs/à renouveler/en risque/MRR).

Couvre :
- ``tableau_de_bord_contrats`` : total, répartition par statut/type, actifs,
  à renouveler, en risque, valeur active/totale, MRR (échéanciers actifs).
- ``mrr_contrats`` : normalisation mensuelle par périodicité.
- ``contrats_en_risque`` : suspendus / préavis dû / résiliation active.
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

from apps.contrats import selectors, services
from apps.contrats.models import Contrat, EcheancierContrat, PartieContrat

User = get_user_model()

TDB = "/api/django/contrats/contrats/tableau-de-bord/"


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
                 date_fin=None, parties=False):
    c = Contrat.objects.create(
        company=company, objet="C", montant=Decimal(montant),
        type_contrat=type_contrat, statut=statut,
        date_debut=timezone.localdate() - timedelta(days=30),
        date_fin=date_fin)
    if parties:
        PartieContrat.objects.create(
            company=company, contrat=c, type_partie="client", nom="X", ordre=0)
        PartieContrat.objects.create(
            company=company, contrat=c, type_partie="prestataire", nom="Y",
            ordre=1)
    return c


class DashboardSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("tdb-svc", "TdbSvc")

    def test_agregats_de_base(self):
        make_contrat(self.co, statut="actif", montant="10000")
        make_contrat(self.co, statut="actif", montant="20000")
        make_contrat(self.co, statut="brouillon", montant="5000")
        data = selectors.tableau_de_bord_contrats(self.co)
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["actifs"], 2)
        self.assertEqual(data["valeur_active"], Decimal("30000"))
        self.assertEqual(data["valeur_totale"], Decimal("35000"))
        self.assertEqual(data["par_statut"].get("actif"), 2)

    def test_mrr_normalise_par_periodicite(self):
        contrat = make_contrat(self.co, statut="actif")
        # Échéancier annuel actif de 12000 → MRR 1000/mois.
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat, periodicite="annuelle",
            statut="actif", facturation_active=True,
            montant_total=Decimal("12000"))
        # Échéancier mensuel actif de 500 → MRR 500/mois.
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat, periodicite="mensuelle",
            statut="actif", facturation_active=True,
            montant_total=Decimal("500"))
        # Échéancier unique → ignoré dans le MRR.
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat, periodicite="unique",
            statut="actif", facturation_active=True,
            montant_total=Decimal("9999"))
        self.assertEqual(selectors.mrr_contrats(self.co), Decimal("1500.00"))

    def test_mrr_ignore_facturation_inactive(self):
        contrat = make_contrat(self.co, statut="actif")
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat, periodicite="mensuelle",
            statut="actif", facturation_active=False,
            montant_total=Decimal("500"))
        self.assertEqual(selectors.mrr_contrats(self.co), Decimal("0.00"))

    def test_en_risque_suspendu_et_resiliation(self):
        make_contrat(self.co, statut="suspendu")
        c2 = make_contrat(self.co, statut="actif", parties=True)
        services.resilier_contrat(c2)  # crée une résiliation active + resilie
        # c2 devient resilie (terminal) → exclu ; mais il porte une résiliation
        # active. La garde exclut les terminaux, donc seul le suspendu reste.
        en_risque = selectors.contrats_en_risque(self.co)
        statuts = set(en_risque.values_list("statut", flat=True))
        self.assertIn("suspendu", statuts)
        self.assertNotIn("resilie", statuts)


class DashboardApiTests(TestCase):
    def setUp(self):
        self.co = make_company("tdb-api", "TdbApi")
        self.admin = make_user(self.co, "tdb-api-admin", role="admin")

    def test_endpoint(self):
        make_contrat(self.co, statut="actif", montant="10000")
        api = auth(self.admin)
        res = api.get(TDB)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["actifs"], 1)
        self.assertEqual(res.data["valeur_active"], "10000.00")
        self.assertIn("mrr", res.data)

    def test_scope_societe(self):
        make_contrat(self.co, statut="actif", montant="10000")
        autre_co = make_company("tdb-api-2", "TdbApi2")
        make_contrat(autre_co, statut="actif", montant="99999")
        autre_admin = make_user(autre_co, "tdb-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(TDB)
        self.assertEqual(res.data["valeur_active"], "99999.00")

    def test_role_gate(self):
        commercial = make_user(self.co, "tdb-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(TDB).status_code, 403)
