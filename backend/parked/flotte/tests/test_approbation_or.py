"""Tests XFLT19 — Approbation des devis de réparation externe.

Couvre :
- Service ``transition_statut_or_autorisee`` : devis > seuil non approuvé →
  bloqué (avec message) ; devis <= seuil → toujours libre ; devis > seuil
  mais statut déjà approuve → libre ; sans devis → libre (chaîne existante
  ouvert/en_cours/clôturé intacte).
- Service ``approuver_ordre_reparation`` : exige devis_recu, pose
  approuve_par/date_approbation.
- Service ``cloturer_ordre_reparation`` + ``ecart_facture_devis_alerte`` :
  écart calculé et journalisé ; > 10 % signalé.
- Endpoint ``PATCH /ordres-reparation/<id>/`` : passage en en_cours refusé
  (400 FR) au-dessus du seuil sans approbation.
- Endpoint ``POST /ordres-reparation/<id>/approuver/`` : 400 si mauvais
  statut, sinon approuve.
- Endpoint ``POST /ordres-reparation/<id>/cloturer/`` : écart >10 % signalé
  à la clôture (``ecart_alerte``).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    OrdreReparation,
    ParametreApprobationOR,
    Vehicule,
)
from apps.flotte.services import (
    approuver_ordre_reparation,
    cloturer_ordre_reparation,
    ecart_facture_devis_alerte,
    transition_statut_or_autorisee,
)

User = get_user_model()

URL_OR = "/api/django/flotte/ordres-reparation/"


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


def make_actif(company, immat="APR-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def make_or(
        company, actif, statut=OrdreReparation.Statut.OUVERT,
        montant_devis=None):
    return OrdreReparation.objects.create(
        company=company, actif_flotte=actif, statut=statut,
        date_ouverture=datetime.date(2026, 6, 1), montant_devis=montant_devis)


class TransitionStatutServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("apr-svc", "Apr Svc")
        self.actif = make_actif(self.co)

    def test_devis_au_dessus_seuil_non_approuve_bloque(self):
        ordre = make_or(self.co, self.actif, montant_devis=8000)
        ok, message = transition_statut_or_autorisee(
            ordre, OrdreReparation.Statut.EN_COURS)
        self.assertFalse(ok)
        self.assertIn("approuvé", message)

    def test_devis_sous_seuil_toujours_libre(self):
        ordre = make_or(self.co, self.actif, montant_devis=2000)
        ok, _ = transition_statut_or_autorisee(
            ordre, OrdreReparation.Statut.EN_COURS)
        self.assertTrue(ok)

    def test_devis_au_dessus_seuil_deja_approuve_libre(self):
        ordre = make_or(
            self.co, self.actif, statut=OrdreReparation.Statut.APPROUVE,
            montant_devis=8000)
        ok, _ = transition_statut_or_autorisee(
            ordre, OrdreReparation.Statut.EN_COURS)
        self.assertTrue(ok)

    def test_sans_devis_toujours_libre(self):
        ordre = make_or(self.co, self.actif)
        ok, _ = transition_statut_or_autorisee(
            ordre, OrdreReparation.Statut.EN_COURS)
        self.assertTrue(ok)

    def test_seuil_editable_par_societe(self):
        ParametreApprobationOR.objects.create(
            company=self.co, seuil_approbation=1000)
        ordre = make_or(self.co, self.actif, montant_devis=1500)
        ok, _ = transition_statut_or_autorisee(
            ordre, OrdreReparation.Statut.EN_COURS)
        self.assertFalse(ok)


class ApprouverServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("apr-approuver", "Apr Approuver")
        self.actif = make_actif(self.co)
        self.user = make_user(self.co, "apr-approuver-user")

    def test_approuve_depuis_devis_recu(self):
        ordre = make_or(
            self.co, self.actif, statut=OrdreReparation.Statut.DEVIS_RECU,
            montant_devis=8000)
        ordre = approuver_ordre_reparation(ordre, self.user)
        self.assertEqual(ordre.statut, OrdreReparation.Statut.APPROUVE)
        self.assertEqual(ordre.approuve_par, self.user)
        self.assertIsNotNone(ordre.date_approbation)

    def test_refuse_hors_devis_recu(self):
        ordre = make_or(self.co, self.actif, statut=OrdreReparation.Statut.OUVERT)
        with self.assertRaises(ValueError):
            approuver_ordre_reparation(ordre, self.user)


class EcartFactureDevisServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("apr-ecart", "Apr Ecart")
        self.actif = make_actif(self.co)

    def test_ecart_calcule_et_signale(self):
        ordre = make_or(self.co, self.actif, montant_devis=1000)
        ordre.cout_main_oeuvre = 800
        ordre.cout_pieces = 400  # cout_total = 1200 → écart +20%.
        cloturer_ordre_reparation(ordre)
        self.assertEqual(float(ordre.ecart_facture_devis_pct), 20.0)
        self.assertTrue(ecart_facture_devis_alerte(ordre))

    def test_ecart_sous_seuil_pas_alerte(self):
        ordre = make_or(self.co, self.actif, montant_devis=1000)
        ordre.cout_main_oeuvre = 500
        ordre.cout_pieces = 500  # cout_total = 1000 → écart 0%.
        cloturer_ordre_reparation(ordre)
        self.assertEqual(float(ordre.ecart_facture_devis_pct), 0.0)
        self.assertFalse(ecart_facture_devis_alerte(ordre))

    def test_sans_devis_aucun_ecart(self):
        ordre = make_or(self.co, self.actif)
        cloturer_ordre_reparation(ordre)
        self.assertIsNone(ordre.ecart_facture_devis_pct)
        self.assertFalse(ecart_facture_devis_alerte(ordre))


class ApprobationOrApiTests(TestCase):
    def setUp(self):
        self.co = make_company("apr-api", "Apr Api")
        self.user = make_user(self.co, "apr-api-user")
        self.actif = make_actif(self.co, immat="APR-A1")

    def test_passage_en_cours_refuse_sans_approbation(self):
        ordre = make_or(self.co, self.actif, montant_devis=8000)
        resp = auth(self.user).patch(f"{URL_OR}{ordre.id}/", {
            "statut": "en_cours",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_approuver_endpoint(self):
        ordre = make_or(
            self.co, self.actif, statut=OrdreReparation.Statut.DEVIS_RECU,
            montant_devis=8000)
        resp = auth(self.user).post(f"{URL_OR}{ordre.id}/approuver/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["statut"], "approuve")

    def test_approuver_endpoint_mauvais_statut(self):
        ordre = make_or(self.co, self.actif, statut=OrdreReparation.Statut.OUVERT)
        resp = auth(self.user).post(f"{URL_OR}{ordre.id}/approuver/")
        self.assertEqual(resp.status_code, 400)

    def test_cloturer_signale_ecart(self):
        ordre = make_or(self.co, self.actif, montant_devis=1000)
        ordre.cout_main_oeuvre = 900
        ordre.cout_pieces = 400  # cout_total = 1300 → écart +30%.
        ordre.save()
        resp = auth(self.user).post(f"{URL_OR}{ordre.id}/cloturer/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data["ecart_alerte"])
        self.assertEqual(float(resp.data["ecart_facture_devis_pct"]), 30.0)

    def test_apres_approbation_passage_en_cours_permis(self):
        ordre = make_or(
            self.co, self.actif, statut=OrdreReparation.Statut.APPROUVE,
            montant_devis=8000)
        resp = auth(self.user).patch(f"{URL_OR}{ordre.id}/", {
            "statut": "en_cours",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
