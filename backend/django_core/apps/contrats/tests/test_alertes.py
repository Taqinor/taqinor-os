"""Tests CONTRAT22 — AlerteContrat + rappels via le système de notifications.

Couvre :
- Service ``creer_alerte`` : pose la société côté serveur (celle du contrat).
- Service ``declencher_alertes_contrat`` : dispatche les alertes DUES via le
  point d'entrée ``apps.notifications.services.notify_many`` (MOCKÉ), marque
  ``envoyee`` + ``date_envoi``, et est IDEMPOTENT (aucun double-envoi).
- Isolation multi-tenant (société A ne dispatche pas les alertes de B).
- Transitions de statut (planifiee → envoyee ; annulee jamais dispatchée).
- Semis depuis les sélecteurs CONTRAT20/21 (préavis + renouvellement),
  idempotent.
- Endpoints CRUD + actions ``declencher`` / ``semer-echeances`` (scopés société,
  ``company``/``cree_par`` côté serveur, accès rôle).
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import AlerteContrat, Contrat

User = get_user_model()

BASE = "/api/django/contrats/alertes/"
DECLENCHER = BASE + "declencher/"
SEMER = BASE + "semer-echeances/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="responsable"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def rows(resp):
    data = resp.data
    return data["results"] if isinstance(data, dict) and "results" in data else data


def make_contrat(company, objet="Contrat", **kwargs):
    defaults = {"statut": Contrat.Statut.ACTIF}
    defaults.update(kwargs)
    return Contrat.objects.create(company=company, objet=objet, **defaults)


# Patch cible : on MOCKE le helper de notifications LÀ OÙ il est utilisé
# (import fonction-local dans services). Le chemin canonique reste le module
# de l'app notifications — on s'assure que c'est bien CE point d'entrée qui est
# appelé (frontière cross-app, jamais les modèles/vues de l'app).
NOTIFY_MANY = "apps.notifications.services.notify_many"
RESOLVE = "apps.notifications.services.resolve_recipients"


# ---------------------------------------------------------------------------
# Service — creer_alerte (société côté serveur)
# ---------------------------------------------------------------------------

class CreerAlerteServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("al-creer", "Creer")
        self.contrat = make_contrat(self.co)

    def test_creer_alerte_force_la_societe_du_contrat(self):
        autre = make_company("al-creer-autre", "Autre")
        # Même si on voulait une autre société, c'est celle du contrat qui prime.
        alerte = services.creer_alerte(
            self.contrat,
            type_alerte=AlerteContrat.TypeAlerte.PERSONNALISE,
            date_declenchement=date(2026, 6, 1),
            message="Rappel",
        )
        self.assertEqual(alerte.company_id, self.co.id)
        self.assertNotEqual(alerte.company_id, autre.id)
        self.assertEqual(alerte.statut, AlerteContrat.Statut.PLANIFIEE)
        self.assertIsNone(alerte.date_envoi)

    def test_type_par_defaut_personnalise(self):
        alerte = services.creer_alerte(
            self.contrat, date_declenchement=date(2026, 6, 1))
        self.assertEqual(
            alerte.type_alerte, AlerteContrat.TypeAlerte.PERSONNALISE)


# ---------------------------------------------------------------------------
# Service — declencher_alertes_contrat (dispatch + idempotence)
# ---------------------------------------------------------------------------

class DeclencherServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("al-decl", "Decl")
        self.contrat = make_contrat(self.co, reference="C-001")
        self.today = date(2026, 6, 15)

    def _alerte(self, jour, statut=AlerteContrat.Statut.PLANIFIEE,
                type_alerte=AlerteContrat.TypeAlerte.PREAVIS):
        return AlerteContrat.objects.create(
            company=self.co, contrat=self.contrat, type_alerte=type_alerte,
            date_declenchement=jour, statut=statut)

    def test_dispatch_alerte_due_marque_envoyee(self):
        a = self._alerte(self.today - timedelta(days=1))
        with mock.patch(NOTIFY_MANY, return_value=[object()]) as nm, \
                mock.patch(RESOLVE, return_value=[object()]):
            res = services.declencher_alertes_contrat(self.co, today=self.today)
        self.assertTrue(nm.called)
        # Le point d'entrée notifications est appelé avec un EventType valide.
        args, kwargs = nm.call_args
        self.assertEqual(args[1], "digest")
        self.assertEqual(kwargs.get("company"), self.co)
        a.refresh_from_db()
        self.assertEqual(a.statut, AlerteContrat.Statut.ENVOYEE)
        self.assertIsNotNone(a.date_envoi)
        self.assertEqual(res["nb_envoyees"], 1)
        self.assertEqual(res["nb_notifications"], 1)

    def test_idempotent_pas_de_double_envoi(self):
        self._alerte(self.today - timedelta(days=1))
        with mock.patch(NOTIFY_MANY, return_value=[object()]) as nm, \
                mock.patch(RESOLVE, return_value=[object()]):
            services.declencher_alertes_contrat(self.co, today=self.today)
            premier = nm.call_count
            # Second passage : plus aucune alerte planifiée due.
            res2 = services.declencher_alertes_contrat(self.co, today=self.today)
        self.assertEqual(premier, 1)
        self.assertEqual(nm.call_count, 1)  # pas de nouvel appel
        self.assertEqual(res2["nb_dues"], 0)
        self.assertEqual(res2["nb_envoyees"], 0)

    def test_alerte_future_non_dispatchee(self):
        a = self._alerte(self.today + timedelta(days=5))
        with mock.patch(NOTIFY_MANY) as nm, mock.patch(RESOLVE, return_value=[]):
            res = services.declencher_alertes_contrat(self.co, today=self.today)
        self.assertFalse(nm.called)
        a.refresh_from_db()
        self.assertEqual(a.statut, AlerteContrat.Statut.PLANIFIEE)
        self.assertEqual(res["nb_dues"], 0)

    def test_alerte_annulee_jamais_dispatchee(self):
        a = self._alerte(
            self.today - timedelta(days=1),
            statut=AlerteContrat.Statut.ANNULEE)
        with mock.patch(NOTIFY_MANY) as nm, mock.patch(RESOLVE, return_value=[]):
            services.declencher_alertes_contrat(self.co, today=self.today)
        self.assertFalse(nm.called)
        a.refresh_from_db()
        self.assertEqual(a.statut, AlerteContrat.Statut.ANNULEE)

    def test_envoyee_meme_sans_destinataire(self):
        # Aucun destinataire : l'alerte est tout de même marquée envoyée (sinon
        # re-tentée indéfiniment) ; la diffusion best-effort ne lève pas.
        a = self._alerte(self.today - timedelta(days=1))
        with mock.patch(NOTIFY_MANY, return_value=[]) as nm, \
                mock.patch(RESOLVE, return_value=[]):
            res = services.declencher_alertes_contrat(self.co, today=self.today)
        self.assertTrue(nm.called)
        a.refresh_from_db()
        self.assertEqual(a.statut, AlerteContrat.Statut.ENVOYEE)
        self.assertEqual(res["nb_notifications"], 0)

    def test_dispatch_qui_leve_n_interrompt_pas(self):
        # Une erreur de diffusion ne casse pas le balayage : l'alerte est quand
        # même marquée envoyée (best-effort avalé).
        a = self._alerte(self.today - timedelta(days=1))
        with mock.patch(NOTIFY_MANY, side_effect=RuntimeError("boom")), \
                mock.patch(RESOLVE, return_value=[object()]):
            res = services.declencher_alertes_contrat(self.co, today=self.today)
        a.refresh_from_db()
        self.assertEqual(a.statut, AlerteContrat.Statut.ENVOYEE)
        self.assertEqual(res["nb_envoyees"], 1)

    def test_isolation_societe(self):
        autre = make_company("al-decl-autre", "Autre")
        autre_contrat = make_contrat(autre, reference="A-001")
        AlerteContrat.objects.create(
            company=autre, contrat=autre_contrat,
            type_alerte=AlerteContrat.TypeAlerte.PREAVIS,
            date_declenchement=self.today - timedelta(days=1))
        with mock.patch(NOTIFY_MANY, return_value=[object()]) as nm, \
                mock.patch(RESOLVE, return_value=[object()]):
            res = services.declencher_alertes_contrat(self.co, today=self.today)
        # La société self.co n'a aucune alerte due → rien dispatché.
        self.assertFalse(nm.called)
        self.assertEqual(res["nb_dues"], 0)


# ---------------------------------------------------------------------------
# Service — semer_alertes_echeances (CONTRAT20/21)
# ---------------------------------------------------------------------------

class SemerServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("al-semer", "Semer")
        self.today = date(2026, 6, 1)

    def test_seme_preavis_et_echeance(self):
        # Échéance préavis = date_fin(2026-06-25) − 10 = 2026-06-15 (dans 14 j).
        c = make_contrat(
            self.co, date_fin=date(2026, 6, 25), preavis_jours=10)
        res = services.semer_alertes_echeances(
            self.co, within_days=30, today=self.today)
        types = set(
            AlerteContrat.objects.filter(contrat=c)
            .values_list("type_alerte", flat=True))
        self.assertIn(AlerteContrat.TypeAlerte.PREAVIS, types)
        self.assertIn(AlerteContrat.TypeAlerte.ECHEANCE, types)
        self.assertGreaterEqual(res["nb_creees"], 2)
        # Date de l'alerte préavis = échéance de préavis.
        preavis = AlerteContrat.objects.get(
            contrat=c, type_alerte=AlerteContrat.TypeAlerte.PREAVIS)
        self.assertEqual(preavis.date_declenchement, date(2026, 6, 15))

    def test_semis_idempotent(self):
        make_contrat(self.co, date_fin=date(2026, 6, 25), preavis_jours=10)
        services.semer_alertes_echeances(
            self.co, within_days=30, today=self.today)
        n1 = AlerteContrat.objects.filter(company=self.co).count()
        res2 = services.semer_alertes_echeances(
            self.co, within_days=30, today=self.today)
        n2 = AlerteContrat.objects.filter(company=self.co).count()
        self.assertEqual(n1, n2)
        self.assertEqual(res2["nb_creees"], 0)


# ---------------------------------------------------------------------------
# API — CRUD + actions
# ---------------------------------------------------------------------------

class AlerteApiTests(TestCase):
    def setUp(self):
        self.co = make_company("al-api", "Api")
        self.other = make_company("al-api-other", "Other")
        self.admin = make_user(self.co, "al-api-admin", role="admin")
        self.contrat = make_contrat(self.co, reference="C-API")
        self.autre_contrat = make_contrat(self.other, reference="O-API")

    def test_create_force_company_et_cree_par(self):
        api = auth(self.admin)
        resp = api.post(BASE, {
            "contrat": self.contrat.id,
            "type_alerte": "personnalise",
            "date_declenchement": "2026-06-01",
            "message": "Rappel manuel",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        a = AlerteContrat.objects.get(id=resp.data["id"])
        self.assertEqual(a.company_id, self.co.id)
        self.assertEqual(a.cree_par_id, self.admin.id)
        self.assertEqual(a.statut, AlerteContrat.Statut.PLANIFIEE)

    def test_create_contrat_autre_societe_refuse(self):
        api = auth(self.admin)
        resp = api.post(BASE, {
            "contrat": self.autre_contrat.id,
            "date_declenchement": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_statut_non_modifiable_via_api(self):
        # statut est read-only : un POST avec statut=envoyee reste planifiee.
        api = auth(self.admin)
        resp = api.post(BASE, {
            "contrat": self.contrat.id,
            "date_declenchement": "2026-06-01",
            "statut": "envoyee",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        a = AlerteContrat.objects.get(id=resp.data["id"])
        self.assertEqual(a.statut, AlerteContrat.Statut.PLANIFIEE)

    def test_list_scopee_societe(self):
        AlerteContrat.objects.create(
            company=self.co, contrat=self.contrat,
            date_declenchement=date(2026, 6, 1))
        AlerteContrat.objects.create(
            company=self.other, contrat=self.autre_contrat,
            date_declenchement=date(2026, 6, 1))
        api = auth(self.admin)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        company_ids = {
            AlerteContrat.objects.get(id=r["id"]).company_id
            for r in rows(resp)
        }
        self.assertEqual(company_ids, {self.co.id})

    def test_action_declencher_dispatch_et_marque(self):
        AlerteContrat.objects.create(
            company=self.co, contrat=self.contrat,
            type_alerte=AlerteContrat.TypeAlerte.PREAVIS,
            date_declenchement=date.today() - timedelta(days=1))
        api = auth(self.admin)
        with mock.patch(NOTIFY_MANY, return_value=[object()]) as nm, \
                mock.patch(RESOLVE, return_value=[object()]):
            resp = api.post(DECLENCHER, {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(nm.called)
        self.assertEqual(resp.data["nb_envoyees"], 1)

    def test_action_semer_cree_alertes(self):
        make_contrat(
            self.co, objet="proche",
            date_fin=date.today() + timedelta(days=20), preavis_jours=5)
        api = auth(self.admin)
        resp = api.post(SEMER, {"within": 60}, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertGreaterEqual(resp.data["nb_creees"], 1)

    def test_role_normal_interdit(self):
        normal = make_user(self.co, "al-api-normal", role="commercial")
        api = auth(normal)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 403)
