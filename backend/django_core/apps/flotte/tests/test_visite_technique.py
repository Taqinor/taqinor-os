"""Tests FLOTTE22 — VisiteTechnique (visite technique, validité paramétrable).

Couvre :
- Modèle ``VisiteTechnique`` :
  - validations ``clean`` (société de l'actif, coût négatif) ;
  - calcul de ``date_prochaine`` = date_visite + validite_mois (paramétrable,
    débordement fin de mois) ;
  - ``statut_calcule(today)`` (valide / a_renouveler / expiree), date injectable.
- Selectors :
  - ``visites_techniques_de_la_societe(company, ...)`` — scope société, filtres ;
  - ``visites_techniques_expirantes(company, within, today=...)``.
- Endpoints API ``/visites-techniques/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - date_prochaine calculée côté serveur ;
  - filtres ``?statut=`` / ``?actif_flotte=`` ;
  - action ``expirantes/?within=N`` (lecture).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, Vehicule, VisiteTechnique
from apps.flotte.selectors import (
    visites_techniques_de_la_societe,
    visites_techniques_expirantes,
)

User = get_user_model()

URL = "/api/django/flotte/visites-techniques/"
URL_EXPIRANTES = "/api/django/flotte/visites-techniques/expirantes/"


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


def make_actif(company, immat="VT-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Modèle : validations + calcul prochaine + statut calculé ───────────────────

class VisiteTechniqueModelTests(TestCase):
    def setUp(self):
        self.co = make_company("vt-model", "VT Model")
        self.actif = make_actif(self.co, "VMOD")

    def test_creation_calcule_date_prochaine_defaut_12(self):
        vt = VisiteTechnique(
            company=self.co, actif_flotte=self.actif,
            centre="CT Casablanca",
            date_visite=datetime.date(2026, 1, 15))
        vt.full_clean()
        vt.save()
        # 12 mois par défaut → +1 an.
        self.assertEqual(vt.validite_mois, 12)
        self.assertEqual(vt.date_prochaine, datetime.date(2027, 1, 15))
        self.assertEqual(vt.statut, VisiteTechnique.Statut.VALIDE)

    def test_validite_parametrable_24_mois(self):
        vt = VisiteTechnique(
            company=self.co, actif_flotte=self.actif,
            centre="CT", date_visite=datetime.date(2026, 1, 15),
            validite_mois=24)
        vt.full_clean()
        self.assertEqual(vt.date_prochaine, datetime.date(2028, 1, 15))

    def test_calcul_debordement_fin_de_mois(self):
        # 31 janv. + 1 mois → 28 févr. (2026 non bissextile).
        self.assertEqual(
            VisiteTechnique.calculer_date_prochaine(
                datetime.date(2026, 1, 31), 1),
            datetime.date(2026, 2, 28))
        # 31 déc. + 12 mois → 31 déc. année suivante.
        self.assertEqual(
            VisiteTechnique.calculer_date_prochaine(
                datetime.date(2025, 12, 31), 12),
            datetime.date(2026, 12, 31))

    def test_date_prochaine_explicite_respectee(self):
        vt = VisiteTechnique(
            company=self.co, actif_flotte=self.actif, centre="CT",
            date_visite=datetime.date(2026, 1, 15),
            date_prochaine=datetime.date(2026, 6, 30))
        vt.full_clean()
        self.assertEqual(vt.date_prochaine, datetime.date(2026, 6, 30))

    def test_actif_autre_societe_rejete(self):
        autre = make_company("vt-model-b", "VT Model B")
        actif_b = make_actif(autre, "B")
        vt = VisiteTechnique(
            company=self.co, actif_flotte=actif_b, centre="CT",
            date_visite=datetime.date(2026, 1, 15))
        with self.assertRaises(ValidationError):
            vt.full_clean()

    def test_cout_negatif_rejete(self):
        vt = VisiteTechnique(
            company=self.co, actif_flotte=self.actif, centre="CT",
            date_visite=datetime.date(2026, 1, 15), cout=-5)
        with self.assertRaises(ValidationError):
            vt.full_clean()

    def test_statut_calcule_expiree(self):
        today = datetime.date(2026, 6, 15)
        vt = VisiteTechnique(
            company=self.co, actif_flotte=self.actif, centre="CT",
            date_visite=datetime.date(2025, 6, 1),
            date_prochaine=datetime.date(2026, 6, 1), alerte_jours=30)
        self.assertEqual(
            vt.statut_calcule(today=today),
            VisiteTechnique.Statut.EXPIREE)

    def test_statut_calcule_a_renouveler(self):
        today = datetime.date(2026, 6, 15)
        # prochaine dans 20 j, marge 30 j → à renouveler.
        vt = VisiteTechnique(
            company=self.co, actif_flotte=self.actif, centre="CT",
            date_visite=datetime.date(2025, 7, 5),
            date_prochaine=datetime.date(2026, 7, 5), alerte_jours=30)
        self.assertEqual(
            vt.statut_calcule(today=today),
            VisiteTechnique.Statut.A_RENOUVELER)

    def test_statut_calcule_valide(self):
        today = datetime.date(2026, 6, 15)
        # prochaine dans 100 j, marge 30 j → valide.
        vt = VisiteTechnique(
            company=self.co, actif_flotte=self.actif, centre="CT",
            date_visite=datetime.date(2025, 9, 23),
            date_prochaine=datetime.date(2026, 9, 23), alerte_jours=30)
        self.assertEqual(
            vt.statut_calcule(today=today),
            VisiteTechnique.Statut.VALIDE)


# ── Selectors : scope société + expirantes (date injectable) ───────────────────

class VisiteTechniqueSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("vt-sel", "VT Sel")
        self.actif = make_actif(self.co, "VSEL")
        self.today = datetime.date(2026, 6, 15)

        # Expirée (overdue).
        self.exp = VisiteTechnique.objects.create(
            company=self.co, actif_flotte=self.actif, centre="A",
            date_visite=datetime.date(2025, 6, 1),
            date_prochaine=datetime.date(2026, 6, 1), alerte_jours=30)
        # Imminente — dans 10 j.
        self.upc = VisiteTechnique.objects.create(
            company=self.co, actif_flotte=self.actif, centre="B",
            date_visite=datetime.date(2025, 6, 25),
            date_prochaine=datetime.date(2026, 6, 25), alerte_jours=30)
        # Valide — dans 200 j.
        self.ok = VisiteTechnique.objects.create(
            company=self.co, actif_flotte=self.actif, centre="C",
            date_visite=datetime.date(2026, 1, 1),
            date_prochaine=datetime.date(2027, 1, 1), alerte_jours=30)

    def test_scope_societe(self):
        autre = make_company("vt-sel-b", "VT Sel B")
        actif_b = make_actif(autre, "B")
        VisiteTechnique.objects.create(
            company=autre, actif_flotte=actif_b, centre="X",
            date_visite=datetime.date(2025, 6, 1),
            date_prochaine=datetime.date(2026, 6, 1))
        self.assertEqual(
            visites_techniques_de_la_societe(self.co).count(), 3)
        self.assertEqual(
            visites_techniques_de_la_societe(autre).count(), 1)

    def test_filtre_par_statut(self):
        self.exp.statut = VisiteTechnique.Statut.EXPIREE
        self.exp.save()
        qs = visites_techniques_de_la_societe(
            self.co, statut=VisiteTechnique.Statut.EXPIREE)
        self.assertEqual([v.id for v in qs], [self.exp.id])

    def test_filtre_par_actif(self):
        actif2 = make_actif(self.co, "VSEL-2")
        autre_vt = VisiteTechnique.objects.create(
            company=self.co, actif_flotte=actif2, centre="D",
            date_visite=datetime.date(2026, 1, 1),
            date_prochaine=datetime.date(2026, 12, 1))
        qs = visites_techniques_de_la_societe(
            self.co, actif_flotte_id=actif2.id)
        self.assertEqual([v.id for v in qs], [autre_vt.id])

    def test_expirantes_within(self):
        # within=15 j → expirée + imminente (10 j), pas la "valide".
        qs = visites_techniques_expirantes(
            self.co, within=15, today=self.today)
        ids = {v.id for v in qs}
        self.assertEqual(ids, {self.exp.id, self.upc.id})


# ── API : CRUD scopé + role gate + filtres + action expirantes ────────────────

class VisiteTechniqueApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("vt-a", "VT A")
        self.co_b = make_company("vt-b", "VT B")
        self.admin_a = make_user(self.co_a, "vt-admin-a", "admin")
        self.user_a = make_user(self.co_a, "vt-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_company_server_side_et_prochaine_calculee(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "centre": "CT Rabat",
            "date_visite": "2026-01-15",
            "resultat": "favorable",
            "validite_mois": 12,
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        vt = VisiteTechnique.objects.get()
        self.assertEqual(vt.company_id, self.co_a.id)
        # date_prochaine calculée côté serveur (read-only).
        self.assertEqual(resp.data["date_prochaine"], "2027-01-15")
        self.assertIn("statut_calcule", resp.data)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "centre": "CT",
            "date_visite": "2026-01-15",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(VisiteTechnique.objects.count(), 0)

    def test_actif_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": actif_b.id,
            "centre": "CT",
            "date_visite": "2026-01-15",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_validite_mois_invalide_refuse(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "centre": "CT",
            "date_visite": "2026-01-15",
            "validite_mois": 0,
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=self.actif, centre="A",
            date_visite=datetime.date(2026, 1, 1),
            date_prochaine=datetime.date(2026, 12, 1))
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "vt-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_filtre_par_statut(self):
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=self.actif, centre="A",
            statut="expiree", date_visite=datetime.date(2025, 1, 1),
            date_prochaine=datetime.date(2026, 1, 1))
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=self.actif, centre="B",
            statut="valide", date_visite=datetime.date(2026, 1, 1),
            date_prochaine=datetime.date(2027, 1, 1))
        resp = auth(self.admin_a).get(f"{URL}?statut=expiree")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_actif_flotte(self):
        actif2 = make_actif(self.co_a, "API-2")
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=self.actif, centre="A",
            date_visite=datetime.date(2026, 1, 1),
            date_prochaine=datetime.date(2026, 12, 1))
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=actif2, centre="B",
            date_visite=datetime.date(2026, 1, 1),
            date_prochaine=datetime.date(2026, 12, 1))
        resp = auth(self.admin_a).get(f"{URL}?actif_flotte={self.actif.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_action_read_any_role(self):
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=self.actif, centre="A",
            date_visite=datetime.date(1999, 1, 1),
            date_prochaine=datetime.date(2000, 1, 1))
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=self.actif, centre="B",
            date_visite=datetime.date(2098, 1, 1),
            date_prochaine=datetime.date(2099, 1, 1))
        resp = auth(self.user_a).get(f"{URL_EXPIRANTES}?within=30")
        self.assertEqual(resp.status_code, 200, resp.data)
        # Seule l'expirée tombe dans la fenêtre (within ne capte pas 2099).
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_within_invalide_retombe_30(self):
        VisiteTechnique.objects.create(
            company=self.co_a, actif_flotte=self.actif, centre="A",
            date_visite=datetime.date(1999, 1, 1),
            date_prochaine=datetime.date(2000, 1, 1))
        resp = auth(self.admin_a).get(f"{URL_EXPIRANTES}?within=abc")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
