"""Tests CONTRAT10 — Génération du contrat par fusion (merge tokens).

Couvre :
- ``fusionner`` : remplacement des jetons ``{{ x }}``, jeton inconnu → vide,
  aucun ``{{ ... }}`` brut ne survit, pas d'exécution de code.
- ``contexte_fusion`` : jetons des champs du contrat + parties + clauses.
- ``rendre_contrat`` : usage du corps du modèle lié, repli par défaut, gabarit
  fourni explicitement.
- Endpoint POST /contrats/<id>/rendre/ : rendu scopé société, accès réservé,
  isolation multi-tenant.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    ClauseContrat,
    Contrat,
    ModeleContrat,
    PartieContrat,
)

User = get_user_model()

BASE = "/api/django/contrats/contrats/"


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


# ---------------------------------------------------------------------------
# Unitaires — fusion de jetons
# ---------------------------------------------------------------------------

class FusionUnitTests(TestCase):
    def test_fusionner_remplace_jetons(self):
        out = services.fusionner(
            "Objet : {{ objet }} — {{ reference }}",
            {"objet": "Vente PV", "reference": "C-001"},
        )
        self.assertEqual(out, "Objet : Vente PV — C-001")

    def test_jeton_inconnu_devient_vide(self):
        out = services.fusionner("[{{ inconnu }}]", {"objet": "x"})
        self.assertEqual(out, "[]")

    def test_aucun_jeton_brut_ne_survit(self):
        out = services.fusionner("{{ a }}{{ b }}", {"a": "1"})
        self.assertNotIn("{{", out)
        self.assertNotIn("}}", out)

    def test_gabarit_vide(self):
        self.assertEqual(services.fusionner("", {"objet": "x"}), "")

    def test_espaces_dans_les_accolades(self):
        out = services.fusionner("{{objet}} {{  objet  }}", {"objet": "ok"})
        self.assertEqual(out, "ok ok")


# ---------------------------------------------------------------------------
# contexte_fusion
# ---------------------------------------------------------------------------

class ContexteFusionTests(TestCase):
    def setUp(self):
        self.co = make_company("gen-ctx", "Ctx")
        self.contrat = Contrat.objects.create(
            company=self.co, objet="Contrat O&M", reference="C-2026-001",
            montant=Decimal("12500.00"), devise="MAD",
        )
        PartieContrat.objects.create(
            company=self.co, contrat=self.contrat,
            type_partie=PartieContrat.TypePartie.CLIENT, nom="Ferme Atlas",
            ordre=0,
        )
        PartieContrat.objects.create(
            company=self.co, contrat=self.contrat,
            type_partie=PartieContrat.TypePartie.PRESTATAIRE, nom="Taqinor",
            ordre=1,
        )
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, titre="Garantie",
            corps="Garantie 10 ans.", ordre=1,
        )

    def test_contexte_contient_champs_et_parties(self):
        ctx = services.contexte_fusion(self.contrat)
        self.assertEqual(ctx["objet"], "Contrat O&M")
        self.assertEqual(ctx["reference"], "C-2026-001")
        self.assertEqual(ctx["client"], "Ferme Atlas")
        self.assertEqual(ctx["prestataire"], "Taqinor")
        self.assertIn("Ferme Atlas", ctx["parties"])
        self.assertIn("12 500.00 MAD", ctx["montant"])

    def test_contexte_contient_clauses(self):
        ctx = services.contexte_fusion(self.contrat)
        self.assertIn("Garantie", ctx["clauses"])
        self.assertIn("Garantie 10 ans.", ctx["clauses"])


# ---------------------------------------------------------------------------
# rendre_contrat
# ---------------------------------------------------------------------------

class RendreContratTests(TestCase):
    def setUp(self):
        self.co = make_company("gen-rendre", "Rendre")
        self.modele = ModeleContrat.objects.create(
            company=self.co, nom="Gabarit O&M",
            corps="Contrat {{ objet }} pour {{ client }}.",
        )
        self.contrat = Contrat.objects.create(
            company=self.co, objet="Maintenance", reference="C-9",
            modele=self.modele,
        )
        PartieContrat.objects.create(
            company=self.co, contrat=self.contrat,
            type_partie=PartieContrat.TypePartie.CLIENT, nom="Client X",
        )

    def test_utilise_corps_du_modele_lie(self):
        out = services.rendre_contrat(self.contrat)
        self.assertEqual(out["rendu"], "Contrat Maintenance pour Client X.")
        self.assertEqual(out["gabarit"], self.modele.corps)

    def test_gabarit_explicite_prime(self):
        out = services.rendre_contrat(self.contrat, gabarit="Ref {{ reference }}")
        self.assertEqual(out["rendu"], "Ref C-9")

    def test_repli_gabarit_par_defaut(self):
        contrat = Contrat.objects.create(
            company=self.co, objet="Sans modèle", reference="C-10",
        )
        out = services.rendre_contrat(contrat)
        self.assertIn("Sans modèle", out["rendu"])
        self.assertNotIn("{{", out["rendu"])


# ---------------------------------------------------------------------------
# Endpoint /rendre/
# ---------------------------------------------------------------------------

class RendreEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("gen-ep", "EP")
        self.admin = make_user(self.co, "gen-ep-admin", role="admin")
        self.contrat = Contrat.objects.create(
            company=self.co, objet="Endpoint", reference="C-EP",
        )

    def test_rendre_endpoint(self):
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{self.contrat.id}/rendre/",
            {"gabarit": "Objet={{ objet }}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["rendu"], "Objet=Endpoint")
        self.assertIn("jetons", resp.data)

    def test_rendre_sans_corps_utilise_defaut(self):
        api = auth(self.admin)
        resp = api.post(f"{BASE}{self.contrat.id}/rendre/", {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("Endpoint", resp.data["rendu"])

    def test_role_normal_refuse(self):
        normal = make_user(self.co, "gen-ep-normal", role="normal")
        api = auth(normal)
        resp = api.post(f"{BASE}{self.contrat.id}/rendre/", {}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_isolation_autre_societe_404(self):
        co_b = make_company("gen-ep-b", "B")
        admin_b = make_user(co_b, "gen-ep-admin-b", role="admin")
        api = auth(admin_b)
        resp = api.post(f"{BASE}{self.contrat.id}/rendre/", {}, format="json")
        self.assertEqual(resp.status_code, 404)
