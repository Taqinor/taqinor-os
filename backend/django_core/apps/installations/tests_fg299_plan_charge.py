"""
FG299 — Plan de charge des équipes (capacité vs affecté) — sélecteur
``plan_de_charge_equipes`` + action ``InterventionViewSet.plan_de_charge``.

Le plan de charge compare, sur une fenêtre [debut, fin] inclusive, la CAPACITÉ
de chaque technicien terrain (jours ouvrés × heures/jour) à sa CHARGE AFFECTÉE
(interventions où il est technicien principal OU membre d'équipe, prévues dans
la fenêtre) pour détecter la SUR-RÉSERVATION (sur-booking).

Couvre :
  * la capacité = jours ouvrés (lundi→vendredi) × heures/jour ;
  * la charge affectée par technicien (principal + membre d'équipe, sans
    double-comptage) ;
  * le drapeau de SUR-RÉSERVATION (affecté > capacité) ;
  * le fenêtrage (seules les interventions de la fenêtre comptent) ;
  * le scope société (aucune intervention d'une autre société) ;
  * la garde division-par-zéro (capacité nulle → charge_pct 0, toute
    affectation en sur-réservation) ;
  * l'endpoint ``plan-de-charge``.

Pure agrégation, lecture seule, aucun nouveau modèle.

Run :
    python manage.py test apps.installations.tests_fg299_plan_charge -v2
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.installations.selectors import plan_de_charge_equipes

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg299-co-{n}', defaults={'nom': nom or f'FG299 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg299-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'fg299-{company.id}-{n}@example.invalid')


def make_installation(company):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-{company.id}-{n}',
        client=make_client(company))


def make_intervention(company, installation, date_prevue,
                      technicien=None, equipe=None):
    interv = Intervention.objects.create(
        company=company, installation=installation,
        type_intervention=Intervention.Type.POSE,
        date_prevue=date_prevue, technicien=technicien)
    if equipe:
        interv.equipe.set(equipe)
    return interv


# Une semaine de travail : lundi 2026-06-01 → dimanche 2026-06-07 (5 jours
# ouvrés). Capacité par technicien = 5 × 8 = 40 h.
LUNDI = datetime.date(2026, 6, 1)
MARDI = datetime.date(2026, 6, 2)
MERCREDI = datetime.date(2026, 6, 3)
JEUDI = datetime.date(2026, 6, 4)
VENDREDI = datetime.date(2026, 6, 5)
DIMANCHE = datetime.date(2026, 6, 7)
SEMAINE_FIN = datetime.date(2026, 6, 7)


# ── Sélecteur : capacité vs affecté ───────────────────────────────────────────

class TestPlanChargeSelecteur(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.tech = make_user(self.company)

    def test_capacite_jours_ouvres(self):
        """FG299 — capacité = jours ouvrés (lun→ven) × heures/jour."""
        # Une intervention pour faire apparaître le technicien.
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        res = plan_de_charge_equipes(
            self.company, LUNDI, SEMAINE_FIN, heures_par_jour=8)
        self.assertEqual(res['jours_ouvres'], 5)  # le week-end exclu
        self.assertEqual(res['capacite_heures'], 40.0)
        row = res['techniciens'][0]
        self.assertEqual(row['capacite_heures'], 40.0)

    def test_affecte_count_principal(self):
        """FG299 — charge affectée = nombre d'interventions du technicien
        principal dans la fenêtre."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        make_intervention(self.company, self.inst, MARDI, technicien=self.tech)
        make_intervention(self.company, self.inst, MERCREDI,
                          technicien=self.tech)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        row = res['techniciens'][0]
        self.assertEqual(row['technicien_id'], self.tech.id)
        self.assertEqual(row['affecte_count'], 3)
        self.assertEqual(row['affecte_heures'], 24.0)  # 3 × 8
        self.assertAlmostEqual(row['charge_pct'], 60.0)  # 24 / 40

    def test_affecte_via_equipe_membership(self):
        """FG299 — un membre d'équipe (M2M) compte autant qu'un technicien
        principal."""
        membre = make_user(self.company)
        make_intervention(self.company, self.inst, LUNDI, equipe=[membre])
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        rows = {r['technicien_id']: r for r in res['techniciens']}
        self.assertIn(membre.id, rows)
        self.assertEqual(rows[membre.id]['affecte_count'], 1)

    def test_no_double_count_principal_and_equipe(self):
        """FG299 — un technicien à la fois principal ET membre d'équipe sur la
        même intervention n'est compté qu'UNE fois."""
        make_intervention(self.company, self.inst, LUNDI,
                          technicien=self.tech, equipe=[self.tech])
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        rows = {r['technicien_id']: r for r in res['techniciens']}
        self.assertEqual(rows[self.tech.id]['affecte_count'], 1)


# ── Sur-réservation ───────────────────────────────────────────────────────────

class TestPlanChargeSurReservation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.tech = make_user(self.company)

    def test_sur_reservation_flag(self):
        """FG299 — sur-réservation quand l'affecté dépasse la capacité.
        Fenêtre d'UN seul jour ouvré (capacité 8 h) avec 2 interventions
        (16 h) → sur-booké."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        res = plan_de_charge_equipes(
            self.company, LUNDI, LUNDI, heures_par_jour=8)
        self.assertEqual(res['capacite_heures'], 8.0)
        row = res['techniciens'][0]
        self.assertEqual(row['affecte_heures'], 16.0)
        self.assertTrue(row['sur_reservation'])
        self.assertEqual(res['totaux']['nb_sur_reservation'], 1)

    def test_not_sur_reservation_within_capacity(self):
        """FG299 — pas de sur-réservation tant que l'affecté ≤ capacité."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        res = plan_de_charge_equipes(
            self.company, LUNDI, SEMAINE_FIN, heures_par_jour=8)
        row = res['techniciens'][0]
        self.assertFalse(row['sur_reservation'])
        self.assertEqual(res['totaux']['nb_sur_reservation'], 0)

    def test_zero_capacity_guard(self):
        """FG299 — capacité nulle (fenêtre = un week-end, aucun jour ouvré) :
        charge_pct reste 0 (pas de division par zéro) et toute affectation est
        en sur-réservation."""
        # Samedi 2026-06-06 → dimanche 2026-06-07 : 0 jour ouvré.
        samedi = datetime.date(2026, 6, 6)
        make_intervention(self.company, self.inst, samedi, technicien=self.tech)
        res = plan_de_charge_equipes(
            self.company, samedi, DIMANCHE, heures_par_jour=8)
        self.assertEqual(res['jours_ouvres'], 0)
        self.assertEqual(res['capacite_heures'], 0.0)
        row = res['techniciens'][0]
        self.assertEqual(row['charge_pct'], 0.0)  # pas de ZeroDivisionError
        self.assertTrue(row['sur_reservation'])  # toute charge sur capacité 0


# ── Fenêtrage ─────────────────────────────────────────────────────────────────

class TestPlanChargeFenetre(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.tech = make_user(self.company)

    def test_only_interventions_in_window(self):
        """FG299 — seules les interventions dont date_prevue ∈ [debut, fin]
        comptent."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        # Hors fenêtre (semaine suivante) — ne doit PAS compter.
        make_intervention(self.company, self.inst,
                          datetime.date(2026, 6, 8), technicien=self.tech)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        row = res['techniciens'][0]
        self.assertEqual(row['affecte_count'], 1)

    def test_intervention_sans_date_exclue(self):
        """FG299 — une intervention sans date_prevue n'est pas fenêtrée (exclue
        du plan de charge daté)."""
        make_intervention(self.company, self.inst, None, technicien=self.tech)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['techniciens'], [])

    def test_non_assigne_grouped(self):
        """FG299 — une intervention sans technicien ni équipe est comptée comme
        non assignée (visibilité), jamais en sur-réservation."""
        make_intervention(self.company, self.inst, LUNDI)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['non_assigne_count'], 1)
        self.assertEqual(res['techniciens'], [])
        self.assertEqual(res['totaux']['nb_sur_reservation'], 0)


# ── Scope société ─────────────────────────────────────────────────────────────

class TestPlanChargeTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)

    def test_company_isolation_selector(self):
        """FG299 — le plan de charge ne voit que les interventions de la
        société."""
        # Société B avec sa propre intervention — invisible pour A.
        company_b = make_company()
        inst_b = make_installation(company_b)
        tech_b = make_user(company_b)
        make_intervention(company_b, inst_b, LUNDI, technicien=tech_b)
        # Société A : une intervention.
        tech_a = make_user(self.company)
        make_intervention(self.company, self.inst, LUNDI, technicien=tech_a)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        ids = {r['technicien_id'] for r in res['techniciens']}
        self.assertIn(tech_a.id, ids)
        self.assertNotIn(tech_b.id, ids)

    def test_endpoint_returns_plan(self):
        """FG299 — l'endpoint ``plan-de-charge`` renvoie le plan de charge sur
        la fenêtre passée en paramètres."""
        tech = make_user(self.company)
        make_intervention(self.company, self.inst, LUNDI, technicien=tech)
        make_intervention(self.company, self.inst, MARDI, technicien=tech)
        r = self.api.get(
            f'{BASE}/interventions/plan-de-charge/',
            {'debut': '2026-06-01', 'fin': '2026-06-07',
             'heures_par_jour': '8'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['jours_ouvres'], 5)
        self.assertEqual(r.data['capacite_heures'], 40.0)
        row = next(t for t in r.data['techniciens']
                   if t['technicien_id'] == tech.id)
        self.assertEqual(row['affecte_count'], 2)

    def test_endpoint_default_window_is_current_week(self):
        """FG299 — sans paramètres, la fenêtre défaut = semaine en cours
        (lundi→dimanche), 5 jours ouvrés."""
        r = self.api.get(f'{BASE}/interventions/plan-de-charge/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['jours_ouvres'], 5)

    def test_endpoint_rejects_inverted_window(self):
        """FG299 — une fenêtre inversée (fin < début) est refusée (400)."""
        r = self.api.get(
            f'{BASE}/interventions/plan-de-charge/',
            {'debut': '2026-06-07', 'fin': '2026-06-01'})
        self.assertEqual(r.status_code, 400, r.data)
