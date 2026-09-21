"""Tests FLOTTE16 — EcheanceEntretien (génération d'échéances dues + alertes).

Couvre :
- ``services.generer_echeances_entretien`` :
  - génère une échéance pour un plan DUE (km / heures / date) avec la cible.
  - IDEMPOTENCE : un second passage ne duplique pas l'échéance ouverte ; une
    nouvelle échéance ne renaît qu'après marquage ``fait``.
  - un plan non-DUE (ok) ne génère aucune échéance.
  - isolation multi-tenant (société B ne voit / génère rien de A).
  - alerte best-effort dispatchée (mockée) vers le conducteur affecté ;
    ``alerter=False`` ne dispatche rien ; un plan sans destinataire ne crash pas.
- Selector ``echeances_de_la_societe`` : scope société, filtres statut/ouvertes.
- Endpoint API ``/echeances-entretien/`` :
  - liste due / en retard (scope société, lecture tout rôle).
  - action ``generer`` (écriture responsable/admin ; interdite au rôle normal).
  - création directe (POST collection) refusée (405).
  - avancement du statut (PATCH a_faire → fait).
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    AffectationConducteur,
    Conducteur,
    EcheanceEntretien,
    EnginRoulant,
    PlanEntretien,
    Vehicule,
)
from apps.flotte.selectors import echeances_de_la_societe
from apps.flotte.services import generer_echeances_entretien

User = get_user_model()

URL = "/api/django/flotte/echeances-entretien/"
URL_GENERER = "/api/django/flotte/echeances-entretien/generer/"


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


def make_vehicule(company, immat="EE-1", km=0):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        kilometrage=km)


def make_engin(company, nom="Nacelle", heures=0):
    return EnginRoulant.objects.create(
        company=company, nom=nom, type_engin="nacelle",
        compteur_heures=heures)


def actif_pour_vehicule(company, vehicule):
    return ActifFlotte.objects.create(company=company, vehicule=vehicule)


def actif_pour_engin(company, engin):
    return ActifFlotte.objects.create(company=company, engin=engin)


def plan_km_due(company, actif, type_entretien="vidange"):
    # dernier=10000, intervalle=10000 → prochaine=20000 (véhicule à 25000 = due).
    return PlanEntretien.objects.create(
        company=company, actif_flotte=actif, type_entretien=type_entretien,
        intervalle_km=10000, dernier_km=10000)


# ── Génération depuis un plan dû ──────────────────────────────────────────────

class GenerationTests(TestCase):
    def setUp(self):
        self.co = make_company("ee-gen", "EE Gen")

    def test_genere_echeance_pour_plan_km_due(self):
        veh = make_vehicule(self.co, "KM-D", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        plan = plan_km_due(self.co, actif)

        res = generer_echeances_entretien(self.co, alerter=False)

        self.assertEqual(res["nb_creees"], 1)
        ech = EcheanceEntretien.objects.get(plan=plan)
        self.assertEqual(ech.company_id, self.co.id)
        self.assertEqual(ech.actif_flotte_id, actif.id)
        self.assertEqual(ech.type_entretien, "vidange")
        self.assertEqual(ech.statut, EcheanceEntretien.Statut.A_FAIRE)
        self.assertEqual(ech.due_km, 20000)  # prochaine échéance km

    def test_genere_echeance_heures(self):
        engin = make_engin(self.co, "GE", heures=1200)
        actif = actif_pour_engin(self.co, engin)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="graissage",
            intervalle_heures=500, dernier_heures=0)
        generer_echeances_entretien(self.co, alerter=False)
        ech = EcheanceEntretien.objects.get(type_entretien="graissage")
        self.assertEqual(ech.due_heures, 500)
        self.assertIsNone(ech.due_km)

    def test_genere_echeance_date(self):
        veh = make_vehicule(self.co, "J-D", km=0)
        actif = actif_pour_vehicule(self.co, veh)
        past = datetime.date.today() - datetime.timedelta(days=400)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="controle",
            intervalle_jours=365, derniere_date=past)
        generer_echeances_entretien(self.co, alerter=False)
        ech = EcheanceEntretien.objects.get(type_entretien="controle")
        self.assertEqual(ech.due_le, past + datetime.timedelta(days=365))

    def test_plan_ok_ne_genere_rien(self):
        # km courant 12000, prochaine 20000 → ok (pas due).
        veh = make_vehicule(self.co, "OK", km=12000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="ok",
            intervalle_km=10000, dernier_km=10000, seuil_alerte_km=500)
        res = generer_echeances_entretien(self.co, alerter=False)
        self.assertEqual(res["nb_creees"], 0)
        self.assertEqual(EcheanceEntretien.objects.count(), 0)

    def test_plan_inactif_ne_genere_rien(self):
        veh = make_vehicule(self.co, "INA", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="inactif",
            intervalle_km=10000, dernier_km=10000, actif=False)
        res = generer_echeances_entretien(self.co, alerter=False)
        self.assertEqual(res["nb_creees"], 0)


# ── Idempotence ───────────────────────────────────────────────────────────────

class IdempotenceTests(TestCase):
    def setUp(self):
        self.co = make_company("ee-idem", "EE Idem")
        veh = make_vehicule(self.co, "IDEM", km=25000)
        self.actif = actif_pour_vehicule(self.co, veh)
        self.plan = plan_km_due(self.co, self.actif)

    def test_second_passage_ne_duplique_pas(self):
        generer_echeances_entretien(self.co, alerter=False)
        res2 = generer_echeances_entretien(self.co, alerter=False)
        self.assertEqual(res2["nb_creees"], 0)
        self.assertEqual(res2["nb_existantes"], 1)
        self.assertEqual(
            EcheanceEntretien.objects.filter(plan=self.plan).count(), 1)

    def test_nouvelle_echeance_apres_fait(self):
        generer_echeances_entretien(self.co, alerter=False)
        ech = EcheanceEntretien.objects.get(plan=self.plan)
        # Une fois marquée FAIT, le cycle est rouvert : un nouveau passage crée.
        ech.statut = EcheanceEntretien.Statut.FAIT
        ech.save(update_fields=["statut"])
        res = generer_echeances_entretien(self.co, alerter=False)
        self.assertEqual(res["nb_creees"], 1)
        self.assertEqual(
            EcheanceEntretien.objects.filter(plan=self.plan).count(), 2)

    def test_planifie_bloque_aussi_la_regeneration(self):
        generer_echeances_entretien(self.co, alerter=False)
        ech = EcheanceEntretien.objects.get(plan=self.plan)
        ech.statut = EcheanceEntretien.Statut.PLANIFIE
        ech.save(update_fields=["statut"])
        res = generer_echeances_entretien(self.co, alerter=False)
        self.assertEqual(res["nb_creees"], 0)


# ── Alertes (mockées) ─────────────────────────────────────────────────────────

class AlerteTests(TestCase):
    def setUp(self):
        self.co = make_company("ee-alert", "EE Alert")
        self.veh = make_vehicule(self.co, "AL", km=25000)
        self.actif = actif_pour_vehicule(self.co, self.veh)
        self.plan = plan_km_due(self.co, self.actif)

    def _affecte_conducteur(self):
        user = make_user(self.co, "ee-driver", "normal")
        cond = Conducteur.objects.create(
            company=self.co, user=user, nom="Chauffeur EE")
        AffectationConducteur.objects.create(
            company=self.co, conducteur=cond, vehicule=self.veh,
            date_debut=datetime.date.today(), actif=True)
        return user

    def test_alerte_dispatchee_vers_conducteur(self):
        user = self._affecte_conducteur()
        with mock.patch(
                "apps.notifications.services.notify") as notify:
            generer_echeances_entretien(self.co, alerter=True)
        self.assertTrue(notify.called)
        kwargs = notify.call_args.kwargs
        self.assertEqual(kwargs["user"], user)
        self.assertEqual(kwargs["event_type"], "maintenance_due")
        self.assertEqual(kwargs["company"], self.co)

    def test_alerter_false_ne_dispatche_pas(self):
        self._affecte_conducteur()
        with mock.patch(
                "apps.notifications.services.notify") as notify:
            generer_echeances_entretien(self.co, alerter=False)
        self.assertFalse(notify.called)

    def test_aucun_destinataire_ne_crash_pas(self):
        # Aucun conducteur affecté : génère quand même sans lever.
        with mock.patch(
                "apps.notifications.services.notify") as notify:
            res = generer_echeances_entretien(self.co, alerter=True)
        self.assertEqual(res["nb_creees"], 1)
        self.assertFalse(notify.called)

    def test_alerte_qui_leve_n_interrompt_pas_la_generation(self):
        self._affecte_conducteur()
        with mock.patch(
                "apps.notifications.services.notify",
                side_effect=RuntimeError("boom")):
            res = generer_echeances_entretien(self.co, alerter=True)
        # L'échéance est créée malgré l'échec de l'alerte (best-effort).
        self.assertEqual(res["nb_creees"], 1)


# ── Selector echeances_de_la_societe ──────────────────────────────────────────

class SelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("ee-sel", "EE Sel")
        self.co_b = make_company("ee-sel-b", "EE Sel B")
        veh = make_vehicule(self.co, "SEL", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        self.plan = plan_km_due(self.co, actif)
        generer_echeances_entretien(self.co, alerter=False)

    def test_scoped_to_company(self):
        self.assertEqual(echeances_de_la_societe(self.co).count(), 1)
        self.assertEqual(echeances_de_la_societe(self.co_b).count(), 0)

    def test_filtre_ouvertes(self):
        ech = echeances_de_la_societe(self.co).first()
        ech.statut = EcheanceEntretien.Statut.FAIT
        ech.save(update_fields=["statut"])
        self.assertEqual(
            echeances_de_la_societe(self.co, ouvertes_only=True).count(), 0)
        self.assertEqual(
            echeances_de_la_societe(
                self.co, statut="fait").count(), 1)


# ── Endpoint API ──────────────────────────────────────────────────────────────

class EcheanceApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("ee-api-a", "EE Api A")
        self.co_b = make_company("ee-api-b", "EE Api B")
        self.admin_a = make_user(self.co_a, "ee-admin-a", "admin")
        self.user_a = make_user(self.co_a, "ee-user-a", "normal")
        veh = make_vehicule(self.co_a, "API", km=25000)
        self.actif_a = actif_pour_vehicule(self.co_a, veh)
        self.plan = plan_km_due(self.co_a, self.actif_a)

    def test_generer_action_admin(self):
        resp = auth(self.admin_a).post(URL_GENERER)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["nb_creees"], 1)
        self.assertEqual(EcheanceEntretien.objects.count(), 1)

    def test_generer_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL_GENERER)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(EcheanceEntretien.objects.count(), 0)

    def test_list_scoped_and_read_any_role(self):
        generer_echeances_entretien(self.co_a, alerter=False)
        # Lecture autorisée à tout rôle.
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        types = {r["type_entretien"] for r in rows(resp)}
        self.assertIn("vidange", types)
        # Société B ne voit rien.
        admin_b = make_user(self.co_b, "ee-admin-b", "admin")
        resp_b = auth(admin_b).get(URL)
        self.assertEqual(rows(resp_b), [])

    def test_list_filtre_ouvertes(self):
        generer_echeances_entretien(self.co_a, alerter=False)
        ech = EcheanceEntretien.objects.get()
        ech.statut = EcheanceEntretien.Statut.FAIT
        ech.save(update_fields=["statut"])
        resp = auth(self.admin_a).get(f"{URL}?ouvertes=true")
        self.assertEqual(rows(resp), [])

    def test_create_post_refused(self):
        # Les échéances ne se POSTent pas : POST collection → 405.
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif_a.id, "type_entretien": "x",
        }, format="json")
        self.assertEqual(resp.status_code, 405, resp.data)

    def test_patch_avance_statut(self):
        generer_echeances_entretien(self.co_a, alerter=False)
        ech = EcheanceEntretien.objects.get()
        resp = auth(self.admin_a).patch(
            f"{URL}{ech.id}/", {"statut": "fait"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        ech.refresh_from_db()
        self.assertEqual(ech.statut, EcheanceEntretien.Statut.FAIT)


# ── WIR5 — Beat Celery quotidien (avant : ni beat ni bouton) ──────────────────

class GenererEcheancesEntretienQuotidienTaskTests(TestCase):
    """Couvre ``apps.flotte.tasks.generer_echeances_entretien_quotidien`` :
    matérialise les échéances dues pour chaque société opérationnelle
    (idempotent, isolation par société) et est bien enregistrée au beat
    Celery avec une route explicite (jamais laissée sur `default`)."""

    def setUp(self):
        self.co_a = make_company("ee-task-a", "EE Task A")
        self.co_b = make_company("ee-task-b", "EE Task B")
        veh_a = make_vehicule(self.co_a, "TSK-A", km=25000)
        actif_a = actif_pour_vehicule(self.co_a, veh_a)
        plan_km_due(self.co_a, actif_a)
        veh_b = make_vehicule(self.co_b, "TSK-B", km=1000)
        actif_b = actif_pour_vehicule(self.co_b, veh_b)
        # Société B : plan non dû (aucune échéance ne doit être créée).
        PlanEntretien.objects.create(
            company=self.co_b, actif_flotte=actif_b,
            type_entretien="vidange", intervalle_km=10000, dernier_km=0)

    def test_generates_due_echeances_per_company(self):
        from apps.flotte.tasks import generer_echeances_entretien_quotidien

        resultat = generer_echeances_entretien_quotidien()
        self.assertGreaterEqual(resultat["societes"], 2)
        self.assertEqual(resultat["echeances_creees"], 1)
        self.assertEqual(
            EcheanceEntretien.objects.filter(
                actif_flotte__company=self.co_a).count(), 1)
        self.assertEqual(
            EcheanceEntretien.objects.filter(
                actif_flotte__company=self.co_b).count(), 0)

    def test_idempotent_second_run(self):
        from apps.flotte.tasks import generer_echeances_entretien_quotidien

        generer_echeances_entretien_quotidien()
        resultat = generer_echeances_entretien_quotidien()
        self.assertEqual(resultat["echeances_creees"], 0)
        self.assertEqual(EcheanceEntretien.objects.count(), 1)

    def test_task_registered_in_beat_schedule_and_routes(self):
        from django.conf import settings

        from erp_agentique.celery import app

        task_names = {e["task"] for e in app.conf.beat_schedule.values()}
        self.assertIn(
            "flotte.generer_echeances_entretien_quotidien", task_names)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES[
                "flotte.generer_echeances_entretien_quotidien"]["queue"],
            "scheduled")
