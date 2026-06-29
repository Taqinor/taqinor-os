"""Tests CONTRAT12 — Machine d'états du cycle de vie + transitions gardées.

Couvre :
- Transitions autorisées vs interdites (``changer_statut`` / graphe).
- Gardes : passage en approbation / signature exige ≥2 parties.
- États terminaux (resilie/expire) sans sortie.
- ``statuts_suivants``.
- Endpoint POST /contrats/<id>/changer-statut/ : transition OK, transition
  interdite → 400, garde parties → 400, accès réservé, isolation.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.machine_etats import TransitionInterdite
from apps.contrats.models import Contrat, PartieContrat

User = get_user_model()

BASE = "/api/django/contrats/contrats/"
S = Contrat.Statut


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


def make_contrat(company, statut=S.BROUILLON, parties=2, **kwargs):
    contrat = Contrat.objects.create(
        company=company, objet="Contrat", statut=statut, **kwargs
    )
    roles = [
        PartieContrat.TypePartie.CLIENT,
        PartieContrat.TypePartie.PRESTATAIRE,
        PartieContrat.TypePartie.TEMOIN,
    ]
    for i in range(parties):
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie=roles[i % len(roles)], nom=f"Partie {i}", ordre=i,
        )
    return contrat


# ---------------------------------------------------------------------------
# Unitaires — graphe + gardes
# ---------------------------------------------------------------------------

class MachineEtatsUnitTests(TestCase):
    def setUp(self):
        self.co = make_company("me-unit", "Unit")

    def test_transition_autorisee(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        services.changer_statut(contrat, S.EN_APPROBATION)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, S.EN_APPROBATION)

    def test_transition_interdite_leve(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        with self.assertRaises(TransitionInterdite):
            services.changer_statut(contrat, S.ACTIF)

    def test_garde_parties_bloque_finalisation(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=1)
        with self.assertRaises(TransitionInterdite):
            services.changer_statut(contrat, S.EN_APPROBATION)

    def test_meme_statut_no_op(self):
        contrat = make_contrat(self.co, statut=S.ACTIF, parties=2)
        services.changer_statut(contrat, S.ACTIF)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, S.ACTIF)

    def test_etat_terminal_sans_sortie(self):
        contrat = make_contrat(self.co, statut=S.RESILIE, parties=2)
        self.assertEqual(services.statuts_suivants(contrat), [])
        with self.assertRaises(TransitionInterdite):
            services.changer_statut(contrat, S.ACTIF)

    def test_chemin_complet_brouillon_vers_actif(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        services.changer_statut(contrat, S.EN_APPROBATION)
        services.changer_statut(contrat, S.SIGNE)
        services.changer_statut(contrat, S.ACTIF)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, S.ACTIF)

    def test_statuts_suivants_depuis_actif(self):
        contrat = make_contrat(self.co, statut=S.ACTIF, parties=2)
        suivants = services.statuts_suivants(contrat)
        self.assertIn(S.SUSPENDU, suivants)
        self.assertIn(S.RESILIE, suivants)
        self.assertIn(S.EXPIRE, suivants)
        self.assertNotIn(S.BROUILLON, suivants)


# ---------------------------------------------------------------------------
# Endpoint /changer-statut/
# ---------------------------------------------------------------------------

class ChangerStatutEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("me-ep", "EP")
        self.admin = make_user(self.co, "me-ep-admin", role="admin")

    def test_transition_ok(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{contrat.id}/changer-statut/",
            {"statut": S.EN_APPROBATION},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["statut"], S.EN_APPROBATION)

    def test_transition_interdite_400(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{contrat.id}/changer-statut/",
            {"statut": S.ACTIF},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_garde_parties_400(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=1)
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{contrat.id}/changer-statut/",
            {"statut": S.EN_APPROBATION},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_statut_invalide_400(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        api = auth(self.admin)
        resp = api.post(
            f"{BASE}{contrat.id}/changer-statut/",
            {"statut": "zzz"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_statuts_suivants_endpoint(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        api = auth(self.admin)
        resp = api.get(f"{BASE}{contrat.id}/statuts-suivants/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["statut"], S.BROUILLON)
        self.assertIn(S.EN_APPROBATION, resp.data["suivants"])

    def test_role_normal_refuse(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        normal = make_user(self.co, "me-ep-normal", role="normal")
        api = auth(normal)
        resp = api.post(
            f"{BASE}{contrat.id}/changer-statut/",
            {"statut": S.EN_APPROBATION},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_isolation_autre_societe_404(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        co_b = make_company("me-ep-b", "B")
        admin_b = make_user(co_b, "me-ep-admin-b", role="admin")
        api = auth(admin_b)
        resp = api.post(
            f"{BASE}{contrat.id}/changer-statut/",
            {"statut": S.EN_APPROBATION},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)
