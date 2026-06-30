"""Tests FLOTTE23 — CarteGriseVehicule (carte grise & autorisation de circulation).

Couvre :
- Modèle ``CarteGriseVehicule`` :
  - validation ``clean`` (société de l'actif) ;
  - ``statut_calcule(today)`` (valide / a_renouveler / expiree, et valide quand
    aucune date de validité d'autorisation n'est fournie), date injectable ;
  - stockage des deux ``FileField`` (carte grise + autorisation).
- Selectors :
  - ``cartes_grises_de_la_societe(company, ...)`` — scope société, filtres ;
  - ``cartes_grises_expirantes(company, within, today=...)`` (exclut les cartes
    sans date de validité d'autorisation).
- Endpoints API ``/cartes-grises/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - actif d'une autre société refusé ;
  - filtres ``?statut=`` / ``?actif_flotte=`` ;
  - action ``expirantes/?within=N`` (lecture) ;
  - upload de fichiers (carte grise + autorisation).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, CarteGriseVehicule, Vehicule
from apps.flotte.selectors import (
    cartes_grises_de_la_societe,
    cartes_grises_expirantes,
)

User = get_user_model()

URL = "/api/django/flotte/cartes-grises/"
URL_EXPIRANTES = "/api/django/flotte/cartes-grises/expirantes/"


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


def make_actif(company, immat="CG-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Modèle : validations + statut calculé + fichiers ───────────────────────────

class CarteGriseVehiculeModelTests(TestCase):
    def setUp(self):
        self.co = make_company("cg-model", "CG Model")
        self.actif = make_actif(self.co, "CMOD")

    def test_creation_simple(self):
        cg = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="CG-2026-001",
            date_immatriculation=datetime.date(2020, 5, 1),
            date_mise_circulation=datetime.date(2020, 5, 1))
        self.assertEqual(cg.statut, CarteGriseVehicule.Statut.VALIDE)
        self.assertEqual(cg.numero_carte_grise, "CG-2026-001")

    def test_actif_autre_societe_rejete(self):
        autre = make_company("cg-model-b", "CG Model B")
        actif_b = make_actif(autre, "B")
        cg = CarteGriseVehicule(
            company=self.co, actif_flotte=actif_b,
            numero_carte_grise="P")
        with self.assertRaises(ValidationError):
            cg.full_clean()

    def test_statut_calcule_sans_validite_reste_valide(self):
        today = datetime.date(2026, 6, 15)
        cg = CarteGriseVehicule(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P", alerte_jours=30)
        self.assertEqual(
            cg.statut_calcule(today=today),
            CarteGriseVehicule.Statut.VALIDE)

    def test_statut_calcule_expiree(self):
        today = datetime.date(2026, 6, 15)
        cg = CarteGriseVehicule(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P",
            autorisation_date_validite=datetime.date(2026, 6, 1),
            alerte_jours=30)
        self.assertEqual(
            cg.statut_calcule(today=today),
            CarteGriseVehicule.Statut.EXPIREE)

    def test_statut_calcule_a_renouveler(self):
        today = datetime.date(2026, 6, 15)
        # validité dans 20 j, marge 30 j → à renouveler.
        cg = CarteGriseVehicule(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P",
            autorisation_date_validite=datetime.date(2026, 7, 5),
            alerte_jours=30)
        self.assertEqual(
            cg.statut_calcule(today=today),
            CarteGriseVehicule.Statut.A_RENOUVELER)

    def test_statut_calcule_valide(self):
        today = datetime.date(2026, 6, 15)
        # validité dans 100 j, marge 30 j → valide.
        cg = CarteGriseVehicule(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P",
            autorisation_date_validite=datetime.date(2026, 9, 23),
            alerte_jours=30)
        self.assertEqual(
            cg.statut_calcule(today=today),
            CarteGriseVehicule.Statut.VALIDE)

    def test_fichiers_stockes(self):
        cg = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P",
            carte_grise_fichier=SimpleUploadedFile(
                "cg.pdf", b"%PDF-cg", content_type="application/pdf"),
            autorisation_fichier=SimpleUploadedFile(
                "auto.pdf", b"%PDF-auto", content_type="application/pdf"))
        cg.refresh_from_db()
        self.assertTrue(cg.carte_grise_fichier.name)
        self.assertIn("flotte/cartes_grises/", cg.carte_grise_fichier.name)
        self.assertTrue(cg.autorisation_fichier.name)
        self.assertIn(
            "flotte/autorisations_circulation/",
            cg.autorisation_fichier.name)


# ── Selectors : scope société + filtres + expirantes (date injectable) ─────────

class CarteGriseVehiculeSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("cg-sel", "CG Sel")
        self.actif = make_actif(self.co, "CSEL")
        self.today = datetime.date(2026, 6, 15)

        # Autorisation expirée (overdue).
        self.exp = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P1",
            autorisation_date_validite=datetime.date(2026, 6, 1),
            alerte_jours=30)
        # Imminente — dans 10 j.
        self.upc = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P2",
            autorisation_date_validite=datetime.date(2026, 6, 25),
            alerte_jours=30)
        # Valide — dans 200 j.
        self.ok = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P3",
            autorisation_date_validite=datetime.date(2027, 1, 1),
            alerte_jours=30)
        # Sans date de validité d'autorisation — jamais dans expirantes.
        self.sans = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="P4")

    def test_scope_societe(self):
        autre = make_company("cg-sel-b", "CG Sel B")
        actif_b = make_actif(autre, "B")
        CarteGriseVehicule.objects.create(
            company=autre, actif_flotte=actif_b, numero_carte_grise="PX")
        self.assertEqual(
            cartes_grises_de_la_societe(self.co).count(), 4)
        self.assertEqual(
            cartes_grises_de_la_societe(autre).count(), 1)

    def test_filtre_par_statut(self):
        self.exp.statut = CarteGriseVehicule.Statut.EXPIREE
        self.exp.save()
        qs = cartes_grises_de_la_societe(
            self.co, statut=CarteGriseVehicule.Statut.EXPIREE)
        self.assertEqual([c.id for c in qs], [self.exp.id])

    def test_filtre_par_actif(self):
        actif2 = make_actif(self.co, "CSEL-2")
        autre_cg = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=actif2, numero_carte_grise="P5")
        qs = cartes_grises_de_la_societe(
            self.co, actif_flotte_id=actif2.id)
        self.assertEqual([c.id for c in qs], [autre_cg.id])

    def test_expirantes_within(self):
        # within=15 j → expirée + imminente (10 j), pas la "valide" ni la
        # carte sans date de validité.
        qs = cartes_grises_expirantes(
            self.co, within=15, today=self.today)
        ids = {c.id for c in qs}
        self.assertEqual(ids, {self.exp.id, self.upc.id})

    def test_expirantes_exclut_sans_validite(self):
        qs = cartes_grises_expirantes(
            self.co, within=100000, today=self.today)
        self.assertNotIn(self.sans.id, {c.id for c in qs})


# ── API : CRUD scopé + role gate + filtres + action expirantes + upload ────────

class CarteGriseVehiculeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("cg-a", "CG A")
        self.co_b = make_company("cg-b", "CG B")
        self.admin_a = make_user(self.co_a, "cg-admin-a", "admin")
        self.user_a = make_user(self.co_a, "cg-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "numero_carte_grise": "CG-2026-001",
            "date_immatriculation": "2020-01-01",
            "date_mise_circulation": "2020-01-01",
            "autorisation_circulation_numero": "AUT-99",
            "autorisation_date_validite": "2027-12-31",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        cg = CarteGriseVehicule.objects.get()
        self.assertEqual(cg.company_id, self.co_a.id)
        self.assertIn("statut_calcule", resp.data)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "numero_carte_grise": "P",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(CarteGriseVehicule.objects.count(), 0)

    def test_actif_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": actif_b.id,
            "numero_carte_grise": "P",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_upload_fichiers(self):
        cg_file = SimpleUploadedFile(
            "cg.pdf", b"%PDF-cg", content_type="application/pdf")
        aut_file = SimpleUploadedFile(
            "aut.pdf", b"%PDF-aut", content_type="application/pdf")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "numero_carte_grise": "P",
            "carte_grise_fichier": cg_file,
            "autorisation_fichier": aut_file,
        }, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.data)
        cg = CarteGriseVehicule.objects.get()
        self.assertTrue(cg.carte_grise_fichier.name)
        self.assertTrue(cg.autorisation_fichier.name)

    def test_list_scoped_and_read_any_role(self):
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P")
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "cg-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_update_and_delete(self):
        cg = CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P")
        resp = auth(self.admin_a).patch(
            f"{URL}{cg.id}/", {"numero_carte_grise": "CG-NEW"},
            format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        cg.refresh_from_db()
        self.assertEqual(cg.numero_carte_grise, "CG-NEW")

        resp = auth(self.admin_a).delete(f"{URL}{cg.id}/")
        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertEqual(CarteGriseVehicule.objects.count(), 0)

    def test_filtre_par_statut(self):
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P1", statut="expiree")
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P2", statut="valide")
        resp = auth(self.admin_a).get(f"{URL}?statut=expiree")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_actif_flotte(self):
        actif2 = make_actif(self.co_a, "API-2")
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P1")
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=actif2,
            numero_carte_grise="P2")
        resp = auth(self.admin_a).get(f"{URL}?actif_flotte={self.actif.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_action_read_any_role(self):
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P1",
            autorisation_date_validite=datetime.date(2000, 1, 1))
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P2",
            autorisation_date_validite=datetime.date(2099, 1, 1))
        resp = auth(self.user_a).get(f"{URL_EXPIRANTES}?within=30")
        self.assertEqual(resp.status_code, 200, resp.data)
        # Seule l'expirée tombe dans la fenêtre (within ne capte pas 2099).
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_within_invalide_retombe_30(self):
        CarteGriseVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            numero_carte_grise="P1",
            autorisation_date_validite=datetime.date(2000, 1, 1))
        resp = auth(self.admin_a).get(f"{URL_EXPIRANTES}?within=abc")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
