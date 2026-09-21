"""Tests FG167 — Feuilles de temps par chantier (job-costing main-d'œuvre).

Couvre :
* Création d'une feuille de temps via l'API (company forcée côté serveur).
* Isolation multi-société : un utilisateur de B ne voit pas les feuilles de A.
* Refus d'un employe appartenant à une autre société.
* Filtres : ?employe=, ?installation_id=, ?date=, ?intervention_id=.
* Validation : heures <= 0 refusées.
* Propriété cout_calcule sur le modèle (heures × taux_horaire).
* Sélecteur labour_hours_for_installation : total heures + coût + count.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, FeuilleTemps
from apps.rh import selectors

User = get_user_model()

BASE = '/api/django/rh/feuilles-temps/'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Tech', prenom='Test')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class FeuilleTempsModelTests(TestCase):
    """Tests unitaires sur le modèle FeuilleTemps (propriétés pures)."""

    def setUp(self):
        self.co = make_company('ft-model', 'ModelCo')
        self.emp = make_employe(self.co, 'FM1')

    def test_cout_calcule_heures_fois_taux(self):
        ft = FeuilleTemps(
            company=self.co, employe=self.emp,
            installation_id=1, date='2026-06-28',
            heures=Decimal('8.00'), taux_horaire=Decimal('50.00'))
        self.assertEqual(ft.cout_calcule, Decimal('400.00'))

    def test_cout_calcule_none_sans_taux(self):
        ft = FeuilleTemps(
            company=self.co, employe=self.emp,
            installation_id=1, date='2026-06-28',
            heures=Decimal('8.00'), taux_horaire=None)
        self.assertIsNone(ft.cout_calcule)

    def test_str(self):
        ft = FeuilleTemps(
            company=self.co, employe=self.emp,
            installation_id=42, date='2026-06-28',
            heures=Decimal('7.50'))
        s = str(ft)
        self.assertIn('FM1', s)
        self.assertIn('42', s)
        self.assertIn('7.50', s)


# ---------------------------------------------------------------------------
# API CRUD tests
# ---------------------------------------------------------------------------

class FeuilleTempsApiTests(TestCase):
    """Tests de l'API feuilles-temps : création, company forcée, isolement."""

    def setUp(self):
        self.co_a = make_company('ft-a', 'A')
        self.co_b = make_company('ft-b', 'B')
        self.user_a = make_user(self.co_a, 'ft-user-a')
        self.user_b = make_user(self.co_b, 'ft-user-b')
        self.emp_a = make_employe(self.co_a, 'FA1')
        self.emp_b = make_employe(self.co_b, 'FB1')

    def _payload(self, employe_id, installation_id=10, heures='8.00',
                 date='2026-06-28'):
        return {
            'employe': employe_id,
            'installation_id': installation_id,
            'date': date,
            'heures': heures,
        }

    def test_creation_company_forcee_cote_serveur(self):
        """La société est toujours posée côté serveur — jamais lue du corps."""
        resp = auth(self.user_a).post(
            BASE, self._payload(self.emp_a.id), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ft = FeuilleTemps.objects.get(id=resp.data['id'])
        self.assertEqual(ft.company, self.co_a)

    def test_creation_avec_intervention_et_taux(self):
        payload = self._payload(self.emp_a.id)
        payload.update({'intervention_id': 99, 'taux_horaire': '45.00',
                        'description': 'Pose panneaux'})
        resp = auth(self.user_a).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ft = FeuilleTemps.objects.get(id=resp.data['id'])
        self.assertEqual(ft.intervention_id, 99)
        self.assertEqual(ft.taux_horaire, Decimal('45.00'))

    def test_employe_autre_societe_refuse(self):
        """Un utilisateur de A ne peut pas imputer les heures d'un employé de B."""
        resp = auth(self.user_a).post(
            BASE, self._payload(self.emp_b.id), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_liste(self):
        """La liste des feuilles de A n'est pas visible par l'utilisateur de B."""
        FeuilleTemps.objects.create(
            company=self.co_a, employe=self.emp_a,
            installation_id=1, date='2026-06-28', heures=Decimal('8'))
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_heures_zero_refuse(self):
        """Des heures <= 0 doivent être refusées par la validation."""
        payload = self._payload(self.emp_a.id, heures='0.00')
        resp = auth(self.user_a).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_heures_negatives_refuse(self):
        payload = self._payload(self.emp_a.id, heures='-2.00')
        resp = auth(self.user_a).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_refuse(self):
        """Un rôle 'normal' (non-responsable) doit obtenir un 403."""
        normal = make_user(self.co_a, 'ft-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)


class FeuilleTempsFilterTests(TestCase):
    """Tests des filtres de l'API feuilles-temps."""

    def setUp(self):
        self.co = make_company('ft-filter', 'FilterCo')
        self.user = make_user(self.co, 'ft-filter-user')
        self.emp1 = make_employe(self.co, 'FF1')
        self.emp2 = make_employe(self.co, 'FF2')

        self.ft1 = FeuilleTemps.objects.create(
            company=self.co, employe=self.emp1, installation_id=10,
            date='2026-06-28', heures=Decimal('8'))
        self.ft2 = FeuilleTemps.objects.create(
            company=self.co, employe=self.emp2, installation_id=20,
            date='2026-06-27', heures=Decimal('4'),
            intervention_id=55)
        self.ft3 = FeuilleTemps.objects.create(
            company=self.co, employe=self.emp1, installation_id=10,
            date='2026-06-27', heures=Decimal('6'))

    def test_filtre_employe(self):
        resp = auth(self.user).get(BASE + f'?employe={self.emp1.id}')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.ft1.id, ids)
        self.assertIn(self.ft3.id, ids)
        self.assertNotIn(self.ft2.id, ids)

    def test_filtre_installation_id(self):
        resp = auth(self.user).get(BASE + '?installation_id=20')
        self.assertEqual(resp.status_code, 200)
        result_ids = [r['id'] for r in rows(resp)]
        self.assertEqual(result_ids, [self.ft2.id])

    def test_filtre_date(self):
        resp = auth(self.user).get(BASE + '?date=2026-06-27')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.ft2.id, ids)
        self.assertIn(self.ft3.id, ids)
        self.assertNotIn(self.ft1.id, ids)

    def test_filtre_intervention_id(self):
        resp = auth(self.user).get(BASE + '?intervention_id=55')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [self.ft2.id])


# ---------------------------------------------------------------------------
# Selector tests
# ---------------------------------------------------------------------------

class LabourHoursSelectorTests(TestCase):
    """Tests du sélecteur labour_hours_for_installation (cross-app)."""

    def setUp(self):
        self.co_a = make_company('ft-sel-a', 'SA')
        self.co_b = make_company('ft-sel-b', 'SB')
        self.emp_a = make_employe(self.co_a, 'SA1')
        self.emp_b = make_employe(self.co_b, 'SB1')

        # Installation 100 : société A, deux lignes (une valorisée, une non)
        FeuilleTemps.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=100,
            date='2026-06-28', heures=Decimal('8'),
            taux_horaire=Decimal('50.00'))
        FeuilleTemps.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=100,
            date='2026-06-27', heures=Decimal('4'),
            taux_horaire=None)   # non valorisé
        # Installation 100 mais société B (ne doit pas polluer les totaux de A)
        FeuilleTemps.objects.create(
            company=self.co_b, employe=self.emp_b, installation_id=100,
            date='2026-06-28', heures=Decimal('10'),
            taux_horaire=Decimal('60.00'))
        # Installation différente (200) — ne doit pas compter
        FeuilleTemps.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=200,
            date='2026-06-28', heures=Decimal('5'))

    def test_total_heures_pour_installation(self):
        """Retourne la somme des heures de A pour l'installation 100."""
        result = selectors.labour_hours_for_installation(
            installation_id=100, company=self.co_a)
        self.assertEqual(result['total_heures'], Decimal('12'))  # 8 + 4
        self.assertEqual(result['count'], 2)

    def test_cout_calcule_lignes_valorisees_seulement(self):
        """Le coût n'agrège que les lignes avec taux_horaire renseigné."""
        result = selectors.labour_hours_for_installation(
            installation_id=100, company=self.co_a)
        # Seule la ligne 8h × 50 = 400 est valorisée (la 4h sans taux exclue)
        self.assertEqual(result['total_cout'], Decimal('400.00'))

    def test_isolation_societe(self):
        """La société B n'est pas agrégée dans les totaux de A."""
        result = selectors.labour_hours_for_installation(
            installation_id=100, company=self.co_a)
        # B a 10h sur la même installation : ne doivent pas apparaître
        self.assertEqual(result['total_heures'], Decimal('12'))

    def test_sans_company_agrege_toutes_societes(self):
        """Sans company, le sélecteur agrège toutes les sociétés (reporting)."""
        result = selectors.labour_hours_for_installation(installation_id=100)
        # A: 8+4=12, B: 10 → total 22
        self.assertEqual(result['total_heures'], Decimal('22'))
        self.assertEqual(result['count'], 3)

    def test_installation_vide(self):
        """Une installation sans feuilles retourne des zéros/None cohérents."""
        result = selectors.labour_hours_for_installation(
            installation_id=9999, company=self.co_a)
        self.assertEqual(result['total_heures'], Decimal('0'))
        self.assertIsNone(result['total_cout'])
        self.assertEqual(result['count'], 0)

    def test_cout_none_si_aucune_ligne_valorisee(self):
        """Si aucune ligne n'a de taux, total_cout vaut None (pas 0)."""
        # Crée une installation avec uniquement des lignes sans taux
        FeuilleTemps.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=300,
            date='2026-06-28', heures=Decimal('3'), taux_horaire=None)
        result = selectors.labour_hours_for_installation(
            installation_id=300, company=self.co_a)
        self.assertEqual(result['total_heures'], Decimal('3'))
        self.assertIsNone(result['total_cout'])
