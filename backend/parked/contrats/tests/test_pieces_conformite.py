"""Tests CONTRAT34 — Pièces de conformité (pièces obligatoires & attestations).

Couvre :
- CRUD du registre des pièces, ``company`` posée côté serveur.
- ``marquer_piece_fournie`` : statut + date côté serveur, lien GED LÂCHE,
  ne touche jamais ``Contrat.statut``.
- Sélecteurs : pièces, pièces obligatoires manquantes.
- API : action marquer-fournie, filtres, scope société, rôle.
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
from apps.contrats.models import Contrat, PieceConformite

User = get_user_model()

PIECES = "/api/django/contrats/pieces-conformite/"


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


def make_contrat(company):
    return Contrat.objects.create(
        company=company, objet="Marché", montant=Decimal("50000"),
        type_contrat="vente", statut="actif",
        date_debut=timezone.localdate() - timedelta(days=10))


class PieceServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("piece-svc", "PieceSvc")
        self.user = make_user(self.co, "piece-svc-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_marquer_fournie(self):
        p = PieceConformite.objects.create(
            company=self.co, contrat=self.contrat,
            type_piece="assurance", libelle="RC décennale")
        exp = timezone.localdate() + timedelta(days=365)
        services.marquer_piece_fournie(
            p, ged_document_id=42, date_expiration=exp, auteur=self.user)
        p.refresh_from_db()
        self.assertEqual(p.statut, PieceConformite.Statut.FOURNIE)
        self.assertEqual(p.date_fourniture, timezone.localdate())
        self.assertEqual(p.ged_document_id, 42)
        self.assertEqual(p.date_expiration, exp)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "actif")

    def test_obligatoires_manquantes(self):
        PieceConformite.objects.create(
            company=self.co, contrat=self.contrat, libelle="A",
            obligatoire=True, statut="manquante")
        PieceConformite.objects.create(
            company=self.co, contrat=self.contrat, libelle="B",
            obligatoire=True, statut="fournie")
        PieceConformite.objects.create(
            company=self.co, contrat=self.contrat, libelle="C",
            obligatoire=False, statut="manquante")
        manquantes = selectors.pieces_obligatoires_manquantes(self.contrat)
        self.assertEqual(manquantes.count(), 1)
        self.assertEqual(manquantes.first().libelle, "A")


class PieceSelectorTests(TestCase):
    def test_scope_societe(self):
        co = make_company("piece-sel", "PieceSel")
        contrat = make_contrat(co)
        autre_co = make_company("piece-sel-2", "PieceSel2")
        autre = make_contrat(autre_co)
        PieceConformite.objects.create(
            company=co, contrat=contrat, libelle="A")
        PieceConformite.objects.create(
            company=autre_co, contrat=autre, libelle="B")
        self.assertEqual(
            selectors.pieces_conformite_contrat(contrat).count(), 1)


class PieceApiTests(TestCase):
    def setUp(self):
        self.co = make_company("piece-api", "PieceApi")
        self.admin = make_user(self.co, "piece-api-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_creer_company_serveur(self):
        api = auth(self.admin)
        res = api.post(
            PIECES,
            {"contrat": self.contrat.id, "type_piece": "fiscale",
             "libelle": "Attestation fiscale", "obligatoire": True,
             "company": 999},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        p = PieceConformite.objects.get(id=res.data["id"])
        self.assertEqual(p.company_id, self.co.id)  # pas 999

    def test_action_marquer_fournie(self):
        p = PieceConformite.objects.create(
            company=self.co, contrat=self.contrat, libelle="RIB")
        api = auth(self.admin)
        res = api.post(
            f"{PIECES}{p.id}/marquer-fournie/", {"ged_document_id": 7},
            format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["statut"], "fournie")
        self.assertEqual(res.data["ged_document_id"], 7)
        self.assertIsNotNone(res.data["date_fourniture"])

    def test_filtre_obligatoire(self):
        PieceConformite.objects.create(
            company=self.co, contrat=self.contrat, libelle="A",
            obligatoire=True)
        PieceConformite.objects.create(
            company=self.co, contrat=self.contrat, libelle="B",
            obligatoire=False)
        api = auth(self.admin)
        res = api.get(f"{PIECES}?obligatoire=true")
        self.assertEqual(res.data["count"], 1)

    def test_scope_societe_endpoint(self):
        PieceConformite.objects.create(
            company=self.co, contrat=self.contrat, libelle="A")
        autre_co = make_company("piece-api-2", "PieceApi2")
        autre_admin = make_user(autre_co, "piece-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(f"{PIECES}?contrat={self.contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)

    def test_role_gate(self):
        commercial = make_user(self.co, "piece-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(PIECES).status_code, 403)
