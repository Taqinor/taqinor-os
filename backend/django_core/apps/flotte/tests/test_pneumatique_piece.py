"""Tests FLOTTE18 — Pneumatique + PieceFlotte (suivi pneus & pièces de flotte).

Couvre :
- Modèle ``Pneumatique`` :
  - validations ``clean`` (société du véhicule, dépose < montage, coût négatif) ;
  - transition de statut monté → déposé → usé.
- Modèle ``PieceFlotte`` :
  - ``cout_total`` CALCULÉ (quantité × coût unitaire), lecture seule ;
  - validations ``clean`` (société du véhicule / de l'OR, coût négatif).
- Selector ``synthese_pneus_pieces_vehicule`` : compteurs + coûts combinés,
  scope société (garde-fou : aucune division par zéro).
- Endpoints API ``/pneumatiques/`` et ``/pieces/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - action ``synthese`` (lecture) ;
  - liste par véhicule (filtre) et transition de statut.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    OrdreReparation,
    PieceFlotte,
    Pneumatique,
    Vehicule,
)
from apps.flotte.selectors import synthese_pneus_pieces_vehicule

User = get_user_model()

URL_PNEUS = "/api/django/flotte/pneumatiques/"
URL_PIECES = "/api/django/flotte/pieces/"
URL_SYNTHESE = "/api/django/flotte/pieces/synthese/"


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


def make_vehicule(company, immat="PN-1", km=0):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        kilometrage=km)


def make_or(company, vehicule):
    actif = ActifFlotte.objects.create(company=company, vehicule=vehicule)
    return OrdreReparation.objects.create(
        company=company, actif_flotte=actif,
        date_ouverture=datetime.date.today())


# ── Modèle Pneumatique : validations + transitions ────────────────────────────

class PneumatiqueModelTests(TestCase):
    def setUp(self):
        self.co = make_company("pneu-model", "Pneu Model")
        self.veh = make_vehicule(self.co, "PMOD")

    def test_creation_simple(self):
        pneu = Pneumatique.objects.create(
            company=self.co, vehicule=self.veh, position="av_g",
            marque="Michelin", dimension="205/55 R16",
            date_montage=datetime.date(2026, 1, 1), km_montage=10000,
            cout=800)
        self.assertEqual(pneu.statut, Pneumatique.Statut.MONTE)
        self.assertEqual(float(pneu.cout), 800.0)

    def test_transition_statut(self):
        pneu = Pneumatique.objects.create(
            company=self.co, vehicule=self.veh, position="av_d")
        pneu.statut = Pneumatique.Statut.DEPOSE
        pneu.date_depose = datetime.date(2026, 6, 1)
        pneu.full_clean()
        pneu.save()
        pneu.refresh_from_db()
        self.assertEqual(pneu.statut, Pneumatique.Statut.DEPOSE)
        pneu.statut = Pneumatique.Statut.USE
        pneu.full_clean()
        pneu.save()
        pneu.refresh_from_db()
        self.assertEqual(pneu.statut, Pneumatique.Statut.USE)

    def test_vehicule_autre_societe_rejete(self):
        autre = make_company("pneu-model-b", "Pneu Model B")
        veh_b = make_vehicule(autre, "B")
        pneu = Pneumatique(company=self.co, vehicule=veh_b, position="ar_g")
        with self.assertRaises(ValidationError):
            pneu.full_clean()

    def test_depose_avant_montage_rejete(self):
        pneu = Pneumatique(
            company=self.co, vehicule=self.veh, position="ar_d",
            date_montage=datetime.date(2026, 6, 10),
            date_depose=datetime.date(2026, 6, 1))
        with self.assertRaises(ValidationError):
            pneu.full_clean()

    def test_cout_negatif_rejete(self):
        pneu = Pneumatique(
            company=self.co, vehicule=self.veh, position="secours", cout=-5)
        with self.assertRaises(ValidationError):
            pneu.full_clean()


# ── Modèle PieceFlotte : coût total calculé + validations ─────────────────────

class PieceFlotteModelTests(TestCase):
    def setUp(self):
        self.co = make_company("piece-model", "Piece Model")
        self.veh = make_vehicule(self.co, "PIMOD")

    def test_cout_total_calcule(self):
        piece = PieceFlotte.objects.create(
            company=self.co, vehicule=self.veh, designation="Plaquettes",
            quantite=4, cout_unitaire="120.50")
        self.assertEqual(piece.cout_total, 482.0)

    def test_cout_total_quantite_nulle(self):
        piece = PieceFlotte(
            company=self.co, vehicule=self.veh, designation="X",
            quantite=0, cout_unitaire=100)
        self.assertEqual(piece.cout_total, 0.0)

    def test_vehicule_autre_societe_rejete(self):
        autre = make_company("piece-model-b", "Piece Model B")
        veh_b = make_vehicule(autre, "B")
        piece = PieceFlotte(
            company=self.co, vehicule=veh_b, designation="Filtre", quantite=1)
        with self.assertRaises(ValidationError):
            piece.full_clean()

    def test_or_autre_societe_rejete(self):
        autre = make_company("piece-model-c", "Piece Model C")
        veh_b = make_vehicule(autre, "C")
        or_b = make_or(autre, veh_b)
        piece = PieceFlotte(
            company=self.co, vehicule=self.veh, designation="Courroie",
            quantite=1, ordre_reparation=or_b)
        with self.assertRaises(ValidationError):
            piece.full_clean()

    def test_cout_unitaire_negatif_rejete(self):
        piece = PieceFlotte(
            company=self.co, vehicule=self.veh, designation="Y",
            quantite=1, cout_unitaire=-1)
        with self.assertRaises(ValidationError):
            piece.full_clean()


# ── Selector synthese_pneus_pieces_vehicule ───────────────────────────────────

class SyntheseSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("syn", "Synthese")
        self.co_b = make_company("syn-b", "Synthese B")
        self.veh = make_vehicule(self.co, "S1")

    def test_compteurs_et_couts(self):
        Pneumatique.objects.create(
            company=self.co, vehicule=self.veh, position="av_g",
            statut="monte", cout=800)
        Pneumatique.objects.create(
            company=self.co, vehicule=self.veh, position="av_d",
            statut="monte", cout=800)
        Pneumatique.objects.create(
            company=self.co, vehicule=self.veh, position="secours",
            statut="depose", cout=600)
        PieceFlotte.objects.create(
            company=self.co, vehicule=self.veh, designation="Plaquettes",
            quantite=4, cout_unitaire=100)  # 400
        res = synthese_pneus_pieces_vehicule(self.co, self.veh.id)
        self.assertEqual(res["nb_pneus_montes"], 2)
        self.assertEqual(res["cout_pneus"], 2200.0)
        self.assertEqual(res["nb_pieces"], 1)
        self.assertEqual(res["quantite_pieces"], 4)
        self.assertEqual(res["cout_pieces"], 400.0)
        self.assertEqual(res["cout_total"], 2600.0)

    def test_vehicule_sans_donnees_pas_de_division_par_zero(self):
        res = synthese_pneus_pieces_vehicule(self.co, self.veh.id)
        self.assertEqual(res["nb_pneus_montes"], 0)
        self.assertEqual(res["nb_pieces"], 0)
        self.assertEqual(res["cout_total"], 0.0)

    def test_scoped_to_company(self):
        Pneumatique.objects.create(
            company=self.co, vehicule=self.veh, position="av_g", cout=500)
        # La société B ne voit pas le pneu de A (filtré par company).
        res_b = synthese_pneus_pieces_vehicule(self.co_b, self.veh.id)
        self.assertEqual(res_b["nb_pneus_montes"], 0)
        self.assertEqual(res_b["cout_pneus"], 0.0)


# ── Endpoint API ──────────────────────────────────────────────────────────────

class ApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("pn-api-a", "PN Api A")
        self.co_b = make_company("pn-api-b", "PN Api B")
        self.admin_a = make_user(self.co_a, "pn-admin-a", "admin")
        self.user_a = make_user(self.co_a, "pn-user-a", "normal")
        self.veh = make_vehicule(self.co_a, "API")

    # ── Pneumatiques ──────────────────────────────────────────────────────────

    def test_create_pneu_company_server_side(self):
        resp = auth(self.admin_a).post(URL_PNEUS, {
            "vehicule": self.veh.id,
            "position": "av_g",
            "marque": "Michelin",
            "dimension": "205/55 R16",
            "cout": "800.00",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        pneu = Pneumatique.objects.get()
        self.assertEqual(pneu.company_id, self.co_a.id)

    def test_create_pneu_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL_PNEUS, {
            "vehicule": self.veh.id, "position": "av_g",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(Pneumatique.objects.count(), 0)

    def test_pneu_vehicule_autre_societe_refuse(self):
        veh_b = make_vehicule(self.co_b, "B")
        resp = auth(self.admin_a).post(URL_PNEUS, {
            "vehicule": veh_b.id, "position": "av_g",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_pneu_transition_statut_via_api(self):
        pneu = Pneumatique.objects.create(
            company=self.co_a, vehicule=self.veh, position="av_g")
        resp = auth(self.admin_a).patch(
            f"{URL_PNEUS}{pneu.id}/",
            {"statut": "depose", "date_depose": "2026-06-01"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        pneu.refresh_from_db()
        self.assertEqual(pneu.statut, Pneumatique.Statut.DEPOSE)

    def test_pneu_list_scoped_and_read_any_role(self):
        Pneumatique.objects.create(
            company=self.co_a, vehicule=self.veh, position="av_g")
        resp = auth(self.user_a).get(URL_PNEUS)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "pn-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL_PNEUS)), [])

    def test_pneu_filtre_par_vehicule(self):
        veh2 = make_vehicule(self.co_a, "API-2")
        Pneumatique.objects.create(
            company=self.co_a, vehicule=self.veh, position="av_g")
        Pneumatique.objects.create(
            company=self.co_a, vehicule=veh2, position="av_g")
        resp = auth(self.admin_a).get(f"{URL_PNEUS}?vehicule={self.veh.id}")
        self.assertEqual(len(rows(resp)), 1)

    # ── Pièces ────────────────────────────────────────────────────────────────

    def test_create_piece_company_server_side_and_cout_total(self):
        resp = auth(self.admin_a).post(URL_PIECES, {
            "vehicule": self.veh.id,
            "designation": "Plaquettes avant",
            "reference": "PLQ-123",
            "quantite": 4,
            "cout_unitaire": "120.00",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        piece = PieceFlotte.objects.get()
        self.assertEqual(piece.company_id, self.co_a.id)
        self.assertEqual(resp.data["cout_total"], 480.0)

    def test_create_piece_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL_PIECES, {
            "vehicule": self.veh.id, "designation": "Filtre", "quantite": 1,
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(PieceFlotte.objects.count(), 0)

    def test_piece_vehicule_autre_societe_refuse(self):
        veh_b = make_vehicule(self.co_b, "B")
        resp = auth(self.admin_a).post(URL_PIECES, {
            "vehicule": veh_b.id, "designation": "Filtre", "quantite": 1,
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_piece_list_scoped(self):
        PieceFlotte.objects.create(
            company=self.co_a, vehicule=self.veh, designation="Filtre",
            quantite=1)
        resp = auth(self.user_a).get(URL_PIECES)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "pi-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL_PIECES)), [])

    def test_synthese_action_read_any_role(self):
        Pneumatique.objects.create(
            company=self.co_a, vehicule=self.veh, position="av_g",
            statut="monte", cout=800)
        PieceFlotte.objects.create(
            company=self.co_a, vehicule=self.veh, designation="Plaquettes",
            quantite=2, cout_unitaire=100)  # 200
        resp = auth(self.user_a).get(f"{URL_SYNTHESE}?vehicule={self.veh.id}")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["nb_pneus_montes"], 1)
        self.assertEqual(resp.data["cout_total"], 1000.0)

    def test_synthese_vehicule_obligatoire(self):
        resp = auth(self.admin_a).get(URL_SYNTHESE)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_synthese_vehicule_autre_societe_404(self):
        veh_b = make_vehicule(self.co_b, "B")
        resp = auth(self.admin_a).get(f"{URL_SYNTHESE}?vehicule={veh_b.id}")
        self.assertEqual(resp.status_code, 404, resp.data)
