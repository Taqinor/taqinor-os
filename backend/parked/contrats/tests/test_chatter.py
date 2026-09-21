"""Tests CONTRAT15 — ContratActivity (chatter / journal du contrat).

Couvre :
- Auto-log d'une transition de statut (action ``changer-statut``) — ancien →
  nouveau, type ``log``, auteur et société posés côté serveur.
- Auto-log d'un changement de confidentialité (PATCH) — seul un changement
  effectif journalise (un PATCH sans changement n'écrit rien).
- Auto-log du workflow d'approbation (lancement + approbation/rejet d'une étape).
- Note manuelle (action ``noter``) — auteur/société côté serveur ; note vide 400.
- Timeline ``historique`` ordonnée du plus récent au plus ancien.
- Multi-tenant : entrées scopées société ; le chatter d'un autre contrat ne fuit
  pas ; un contrat d'une autre société est 404.
- Acting-user posé côté serveur (jamais lu du corps).
- Champs valeur en TextField : un instantané long ne lève pas (leçon FG136).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat,
    ContratActivity,
    PartieContrat,
    RegleApprobation,
)

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def make_contrat(company, montant=Decimal("1000"), type_contrat="vente",
                 objet="Contrat test", **kwargs):
    return Contrat.objects.create(
        company=company, objet=objet, montant=montant,
        type_contrat=type_contrat, **kwargs)


def add_deux_parties(contrat):
    """Ajoute client + prestataire (deux parties) — requis pour finaliser."""
    PartieContrat.objects.create(
        company=contrat.company, contrat=contrat,
        type_partie=PartieContrat.TypePartie.CLIENT, nom="Client", ordre=1)
    PartieContrat.objects.create(
        company=contrat.company, contrat=contrat,
        type_partie=PartieContrat.TypePartie.PRESTATAIRE, nom="Presta", ordre=2)


def make_regle(company, libelle="Règle", **kwargs):
    defaults = {
        "type_contrat": "",
        "montant_min": None,
        "montant_max": Decimal("1000000"),
        "niveau_approbation": "responsable",
        "nombre_approbateurs": 1,
        "priorite": 0,
        "actif": True,
    }
    defaults.update(kwargs)
    return RegleApprobation.objects.create(
        company=company, libelle=libelle, **defaults)


# ---------------------------------------------------------------------------
# Service — journalisation directe
# ---------------------------------------------------------------------------

class JournaliserServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ca-svc", "Svc")
        self.user = make_user(self.co, "ca-svc-admin")
        self.contrat = make_contrat(self.co)

    def test_journaliser_transition_cree_entree_log(self):
        act = services.journaliser_transition(
            self.contrat, field="statut", old_value="brouillon",
            new_value="en_approbation", auteur=self.user)
        self.assertEqual(act.type, ContratActivity.Kind.LOG)
        self.assertEqual(act.field, "statut")
        self.assertEqual(act.old_value, "brouillon")
        self.assertEqual(act.new_value, "en_approbation")
        # Société déduite du contrat, auteur passé côté serveur.
        self.assertEqual(act.company_id, self.co.id)
        self.assertEqual(act.auteur_id, self.user.id)

    def test_journaliser_coerce_valeurs_en_chaine(self):
        # Une valeur non-chaîne (None / nombre) ne lève pas.
        act = services.journaliser_transition(
            self.contrat, field="montant", old_value=None, new_value=1000)
        self.assertEqual(act.old_value, "")
        self.assertEqual(act.new_value, "1000")

    def test_valeurs_longues_ne_levent_pas(self):
        # FG136 : old/new sont des TextField — un instantané long passe.
        long_val = "x" * 5000
        act = services.journaliser_transition(
            self.contrat, field="confidentialite", old_value=long_val,
            new_value=long_val)
        act.refresh_from_db()
        self.assertEqual(len(act.old_value), 5000)

    def test_noter_contrat_cree_note(self):
        act = services.noter_contrat(
            self.contrat, message="Relancer le client", auteur=self.user)
        self.assertEqual(act.type, ContratActivity.Kind.NOTE)
        self.assertEqual(act.message, "Relancer le client")
        self.assertEqual(act.company_id, self.co.id)
        self.assertEqual(act.auteur_id, self.user.id)


# ---------------------------------------------------------------------------
# Endpoints — auto-log des transitions
# ---------------------------------------------------------------------------

class AutoLogEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("ca-ep", "EP")
        self.admin = make_user(self.co, "ca-ep-admin")
        self.contrat = make_contrat(self.co)
        add_deux_parties(self.contrat)

    def _url(self, suffix):
        return f"{CONTRATS}{self.contrat.id}/{suffix}/"

    def test_changer_statut_journalise(self):
        api = auth(self.admin)
        resp = api.post(
            self._url("changer-statut"),
            {"statut": "en_approbation"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        act = self.contrat.activites.filter(field="statut").first()
        self.assertIsNotNone(act)
        self.assertEqual(act.type, ContratActivity.Kind.LOG)
        self.assertEqual(act.old_value, "brouillon")
        self.assertEqual(act.new_value, "en_approbation")
        # Auteur = utilisateur courant, posé côté serveur.
        self.assertEqual(act.auteur_id, self.admin.id)
        self.assertEqual(act.company_id, self.co.id)

    def test_transition_interdite_ne_journalise_pas(self):
        api = auth(self.admin)
        # brouillon → signe n'est pas permis → 400, aucun log.
        resp = api.post(
            self._url("changer-statut"),
            {"statut": "signe"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.contrat.activites.count(), 0)

    def test_patch_confidentialite_journalise(self):
        api = auth(self.admin)
        ancien = self.contrat.confidentialite
        cible = "public" if ancien != "public" else "confidentiel"
        resp = api.patch(
            f"{CONTRATS}{self.contrat.id}/",
            {"confidentialite": cible}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        act = self.contrat.activites.filter(field="confidentialite").first()
        self.assertIsNotNone(act)
        self.assertEqual(act.old_value, ancien)
        self.assertEqual(act.new_value, cible)
        self.assertEqual(act.auteur_id, self.admin.id)

    def test_patch_sans_changement_confidentialite_ne_journalise_pas(self):
        api = auth(self.admin)
        # PATCH d'un autre champ sans toucher confidentialite : aucun log.
        resp = api.patch(
            f"{CONTRATS}{self.contrat.id}/",
            {"objet": "Nouvel objet"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            self.contrat.activites.filter(field="confidentialite").exists())

    def test_workflow_approbation_journalise(self):
        make_regle(self.co, nombre_approbateurs=1)
        api = auth(self.admin)
        # Lancement
        resp = api.post(self._url("lancer-approbation"))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            self.contrat.activites.filter(
                field="approbation",
                new_value__contains="workflow lancé").exists())
        # Approbation de l'étape
        etape = self.contrat.etapes_approbation.order_by("niveau").first()
        resp = api.post(
            self._url("approuver-etape"),
            {"etape": etape.id, "commentaire": "OK"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        log = self.contrat.activites.filter(
            field="approbation", new_value__contains="approuve").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.message, "OK")
        self.assertEqual(log.auteur_id, self.admin.id)


# ---------------------------------------------------------------------------
# Endpoints — note manuelle + historique
# ---------------------------------------------------------------------------

class NoterHistoriqueTests(TestCase):
    def setUp(self):
        self.co = make_company("ca-nh", "NH")
        self.admin = make_user(self.co, "ca-nh-admin")
        self.contrat = make_contrat(self.co)

    def _url(self, suffix):
        return f"{CONTRATS}{self.contrat.id}/{suffix}/"

    def test_noter_cree_note_cote_serveur(self):
        api = auth(self.admin)
        resp = api.post(
            self._url("noter"),
            {"message": "À signer cette semaine"}, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["type"], "note")
        self.assertEqual(resp.data["message"], "À signer cette semaine")
        self.assertEqual(resp.data["auteur"], self.admin.id)
        act = self.contrat.activites.get(id=resp.data["id"])
        self.assertEqual(act.company_id, self.co.id)
        self.assertEqual(act.auteur_id, self.admin.id)

    def test_noter_vide_400(self):
        api = auth(self.admin)
        resp = api.post(
            self._url("noter"), {"message": "   "}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.contrat.activites.count(), 0)

    def test_historique_ordonne_du_plus_recent(self):
        # Trois entrées : la timeline renvoie la plus récente en tête.
        services.journaliser_transition(
            self.contrat, field="statut", old_value="brouillon",
            new_value="en_approbation", auteur=self.admin)
        services.noter_contrat(
            self.contrat, message="note 1", auteur=self.admin)
        services.noter_contrat(
            self.contrat, message="note 2", auteur=self.admin)
        api = auth(self.admin)
        resp = api.get(self._url("historique"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 3)
        ids = [e["id"] for e in resp.data]
        self.assertEqual(ids, sorted(ids, reverse=True))


# ---------------------------------------------------------------------------
# Multi-tenant
# ---------------------------------------------------------------------------

class ChatterTenantTests(TestCase):
    def setUp(self):
        self.a = make_company("ca-a", "A")
        self.b = make_company("ca-b", "B")
        self.admin_a = make_user(self.a, "ca-a-admin")
        self.contrat_a = make_contrat(self.a, objet="A")
        self.contrat_b = make_contrat(self.b, objet="B")
        services.noter_contrat(
            self.contrat_a, message="note A", auteur=self.admin_a)
        services.noter_contrat(self.contrat_b, message="note B")

    def test_historique_scope_societe(self):
        api = auth(self.admin_a)
        resp = api.get(f"{CONTRATS}{self.contrat_a.id}/historique/")
        self.assertEqual(resp.status_code, 200)
        messages = {e["message"] for e in resp.data}
        self.assertIn("note A", messages)
        self.assertNotIn("note B", messages)

    def test_contrat_autre_societe_404(self):
        api = auth(self.admin_a)
        resp = api.get(f"{CONTRATS}{self.contrat_b.id}/historique/")
        self.assertEqual(resp.status_code, 404)

    def test_noter_contrat_autre_societe_404(self):
        api = auth(self.admin_a)
        resp = api.post(
            f"{CONTRATS}{self.contrat_b.id}/noter/",
            {"message": "fuite"}, format="json")
        self.assertEqual(resp.status_code, 404)
        # Aucune entrée n'a fui dans le contrat de B.
        self.assertFalse(
            self.contrat_b.activites.filter(message="fuite").exists())


# ---------------------------------------------------------------------------
# Acting-user / société toujours serveur (jamais du corps)
# ---------------------------------------------------------------------------

class ServerSideAttributionTests(TestCase):
    def setUp(self):
        self.co = make_company("ca-ss", "SS")
        self.admin = make_user(self.co, "ca-ss-admin")
        self.autre = make_user(self.co, "ca-ss-autre")
        self.contrat = make_contrat(self.co)

    def test_auteur_et_company_ignores_du_corps(self):
        api = auth(self.admin)
        resp = api.post(
            f"{CONTRATS}{self.contrat.id}/noter/",
            {"message": "x", "auteur": self.autre.id, "company": 9999},
            format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        act = self.contrat.activites.get(id=resp.data["id"])
        # L'auteur reste l'utilisateur authentifié, la société celle du contrat.
        self.assertEqual(act.auteur_id, self.admin.id)
        self.assertEqual(act.company_id, self.co.id)

    def test_role_normal_interdit(self):
        normal = make_user(self.co, "ca-ss-normal", role="commercial")
        api = auth(normal)
        resp = api.get(f"{CONTRATS}{self.contrat.id}/historique/")
        self.assertEqual(resp.status_code, 403)
