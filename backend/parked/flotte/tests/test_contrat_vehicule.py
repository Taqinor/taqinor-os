"""Tests XFLT1 — ContratVehicule (leasing/LLD/location/entretien).

Couvre :
- Modèle ``ContratVehicule`` :
  - validations ``clean`` (société du véhicule/garage, fin < début) ;
  - ``statut_calcule(today)`` (actif / expire), date injectable.
- Selectors :
  - ``contrats_vehicule_de_la_societe(company, ...)`` — scope société, filtres ;
  - ``contrats_vehicule_expirants(company, within, today=...)``.
  - intégration dans ``alertes_echeances_reglementaires`` (6e source).
- Endpoints API ``/contrats-vehicule/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - filtres ``?statut=`` / ``?vehicule=`` ;
  - action ``expirants/?within=N`` (lecture).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ContratVehicule, Garage, Vehicule
from apps.flotte.selectors import (
    alertes_echeances_reglementaires,
    contrats_vehicule_de_la_societe,
    contrats_vehicule_expirants,
)

User = get_user_model()

URL = "/api/django/flotte/contrats-vehicule/"
URL_EXPIRANTS = "/api/django/flotte/contrats-vehicule/expirants/"


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def make_vehicule(company, immat="CV-1"):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")


# ── Modèle : validations + statut calculé ──────────────────────────────────────

class ContratVehiculeModelTests(TestCase):
    def setUp(self):
        self.co = make_company("ctrv-model", "Ctrv Model")
        self.veh = make_vehicule(self.co, "CMOD")

    def test_creation_simple(self):
        ctr = ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh, type_contrat="leasing",
            fournisseur="Wafasalaf", date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2029, 1, 1), montant_recurrent=4500,
            periodicite="mensuel")
        self.assertEqual(ctr.statut, ContratVehicule.Statut.ACTIF)
        self.assertEqual(float(ctr.montant_recurrent), 4500.0)

    def test_vehicule_autre_societe_rejete(self):
        autre = make_company("ctrv-model-b", "Ctrv Model B")
        veh_b = make_vehicule(autre, "B")
        ctr = ContratVehicule(
            company=self.co, vehicule=veh_b, date_debut=datetime.date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            ctr.full_clean()

    def test_garage_autre_societe_rejete(self):
        autre = make_company("ctrv-model-c", "Ctrv Model C")
        garage_b = Garage.objects.create(company=autre, nom="Garage B")
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh, garage=garage_b,
            date_debut=datetime.date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            ctr.full_clean()

    def test_fin_avant_debut_rejete(self):
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 6, 1),
            date_fin=datetime.date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            ctr.full_clean()

    def test_statut_calcule_expire(self):
        today = datetime.date(2026, 6, 15)
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2025, 1, 1),
            date_fin=datetime.date(2026, 6, 1))
        self.assertEqual(
            ctr.statut_calcule(today=today), ContratVehicule.Statut.EXPIRE)

    def test_statut_calcule_actif(self):
        today = datetime.date(2026, 6, 15)
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2025, 1, 1),
            date_fin=datetime.date(2027, 1, 1))
        self.assertEqual(
            ctr.statut_calcule(today=today), ContratVehicule.Statut.ACTIF)

    def test_statut_calcule_sans_date_fin_toujours_actif(self):
        today = datetime.date(2026, 6, 15)
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2020, 1, 1), date_fin=None)
        self.assertEqual(
            ctr.statut_calcule(today=today), ContratVehicule.Statut.ACTIF)


# ── Selectors : scope société + expirants (date injectable) ────────────────────

class ContratVehiculeSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("ctrv-sel", "Ctrv Sel")
        self.veh = make_vehicule(self.co, "CSEL")
        self.today = datetime.date(2026, 6, 15)

        # Expiré (overdue).
        self.exp = ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2024, 1, 1),
            date_fin=datetime.date(2026, 6, 1))
        # Imminent — dans 10 j.
        self.upc = ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2024, 1, 1),
            date_fin=datetime.date(2026, 6, 25))
        # Valide — dans 200 j.
        self.ok = ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2024, 1, 1),
            date_fin=datetime.date(2027, 1, 1))
        # Durée indéterminée — ne remonte jamais.
        self.indetermine = ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2024, 1, 1), date_fin=None)

    def test_scope_societe(self):
        autre = make_company("ctrv-sel-b", "Ctrv Sel B")
        veh_b = make_vehicule(autre, "B")
        ContratVehicule.objects.create(
            company=autre, vehicule=veh_b,
            date_debut=datetime.date(2024, 1, 1))
        self.assertEqual(
            contrats_vehicule_de_la_societe(self.co).count(), 4)
        self.assertEqual(
            contrats_vehicule_de_la_societe(autre).count(), 1)

    def test_filtre_par_statut(self):
        self.exp.statut = ContratVehicule.Statut.EXPIRE
        self.exp.save()
        qs = contrats_vehicule_de_la_societe(
            self.co, statut=ContratVehicule.Statut.EXPIRE)
        self.assertEqual([c.id for c in qs], [self.exp.id])

    def test_filtre_par_vehicule(self):
        veh2 = make_vehicule(self.co, "CSEL-2")
        autre_ctr = ContratVehicule.objects.create(
            company=self.co, vehicule=veh2,
            date_debut=datetime.date(2026, 1, 1))
        qs = contrats_vehicule_de_la_societe(self.co, vehicule_id=veh2.id)
        self.assertEqual([c.id for c in qs], [autre_ctr.id])

    def test_expirants_within(self):
        # within=15 j → expiré + imminent (10 j), pas le "valide" ni
        # l'indéterminé (aucune date_fin).
        qs = contrats_vehicule_expirants(self.co, within=15, today=self.today)
        ids = {c.id for c in qs}
        self.assertEqual(ids, {self.exp.id, self.upc.id})

    def test_indetermine_jamais_dans_expirants(self):
        qs = contrats_vehicule_expirants(
            self.co, within=99999, today=self.today)
        ids = {c.id for c in qs}
        self.assertNotIn(self.indetermine.id, ids)

    def test_integration_alertes_echeances(self):
        """XFLT1 — le contrat expirant remonte comme 6e source dans le moteur
        d'alertes unifié (FLOTTE24), sans écraser les autres sources."""
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        sources = {a['source'] for a in result['alertes']}
        self.assertIn('contrat_vehicule', sources)
        objet_ids = {
            a['objet_id'] for a in result['alertes']
            if a['source'] == 'contrat_vehicule'
        }
        self.assertEqual(objet_ids, {self.exp.id, self.upc.id})


# ── API : CRUD scopé + role gate + filtres + action expirants ─────────────────

class ContratVehiculeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("ctrv-a", "Ctrv A")
        self.co_b = make_company("ctrv-b", "Ctrv B")
        self.admin_a = make_user(self.co_a, "cv-admin-a", "admin")
        self.user_a = make_user(self.co_a, "cv-user-a", "normal")
        self.veh = make_vehicule(self.co_a, "API")

    def test_create_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh.id,
            "type_contrat": "lld",
            "fournisseur": "ALD Automotive",
            "date_debut": "2026-01-01",
            "date_fin": "2029-01-01",
            "montant_recurrent": "3800.00",
            "periodicite": "mensuel",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        ctr = ContratVehicule.objects.get()
        self.assertEqual(ctr.company_id, self.co_a.id)
        self.assertIn("statut_calcule", resp.data)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "vehicule": self.veh.id,
            "date_debut": "2026-01-01",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(ContratVehicule.objects.count(), 0)

    def test_vehicule_autre_societe_refuse(self):
        veh_b = make_vehicule(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "vehicule": veh_b.id,
            "date_debut": "2026-01-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_fin_avant_debut_refuse(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh.id,
            "date_debut": "2026-12-01",
            "date_fin": "2026-01-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1))
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "cv-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_filtre_par_statut(self):
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=self.veh, statut="expire",
            date_debut=datetime.date(2024, 1, 1))
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=self.veh, statut="actif",
            date_debut=datetime.date(2026, 1, 1))
        resp = auth(self.admin_a).get(f"{URL}?statut=expire")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_vehicule(self):
        veh2 = make_vehicule(self.co_a, "API-2")
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1))
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=veh2,
            date_debut=datetime.date(2026, 1, 1))
        resp = auth(self.admin_a).get(f"{URL}?vehicule={self.veh.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_expirants_action_read_any_role(self):
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=self.veh,
            date_debut=datetime.date(2020, 1, 1),
            date_fin=datetime.date(2000, 1, 1))
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2099, 1, 1))
        resp = auth(self.user_a).get(f"{URL_EXPIRANTS}?within=30")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)

    def test_expirants_within_invalide_retombe_30(self):
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=self.veh,
            date_debut=datetime.date(2020, 1, 1),
            date_fin=datetime.date(2000, 1, 1))
        resp = auth(self.admin_a).get(f"{URL_EXPIRANTS}?within=abc")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
