"""Tests de la rémunération de base RH (FG157).

Couvre :
* le gating par la permission ``salaires_voir`` : un porteur d'un rôle SANS la
  permission est refusé en LECTURE et en ÉCRITURE (403) ; un porteur AVEC la
  permission passe (lecture + création) ;
* l'isolation multi-société (A ne voit pas les rémunérations de B) ;
* la société posée côté serveur (jamais lue du corps) ;
* l'ordre de l'historique (plus récent d'abord, par ``date_effet``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.rh.models import DossierEmploye, Remuneration

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, permissions):
    """Crée un utilisateur portant un rôle fin avec exactement ``permissions``."""
    role = Role.objects.create(
        company=company, nom=f'role-{username}', permissions=list(permissions))
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class RemunerationGatingTests(TestCase):
    BASE = '/api/django/rh/remunerations/'

    def setUp(self):
        self.co_a = make_company('rem-a', 'A')
        self.co_b = make_company('rem-b', 'B')
        # Porteur de salaires_voir + un porteur sans la permission.
        self.rh = make_user(self.co_a, 'rh-paie', ['salaires_voir'])
        self.sans = make_user(self.co_a, 'rh-sans', ['crm_voir', 'ventes_voir'])
        self.emp_a = DossierEmploye.objects.create(
            company=self.co_a, matricule='EMP001', nom='Kasri', prenom='Reda')

    def _payload(self, **over):
        data = {
            'employe': self.emp_a.id,
            'montant': '8000.00',
            'periodicite': 'mensuel',
            'date_effet': '2026-01-01',
        }
        data.update(over)
        return data

    # ── Gating LECTURE ──────────────────────────────────────────────────────
    def test_sans_permission_refuse_lecture(self):
        Remuneration.objects.create(
            company=self.co_a, employe=self.emp_a, montant='8000',
            date_effet='2026-01-01')
        resp = auth(self.sans).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_avec_permission_peut_lire(self):
        Remuneration.objects.create(
            company=self.co_a, employe=self.emp_a, montant='8000',
            date_effet='2026-01-01')
        resp = auth(self.rh).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    # ── Gating ÉCRITURE ─────────────────────────────────────────────────────
    def test_sans_permission_refuse_ecriture(self):
        resp = auth(self.sans).post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Remuneration.objects.count(), 0)

    def test_avec_permission_peut_creer(self):
        resp = auth(self.rh).post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Remuneration.objects.get(id=resp.data['id'])
        # Société posée côté serveur, devise par défaut MAD.
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.devise, 'MAD')
        self.assertEqual(obj.employe, self.emp_a)

    def test_company_jamais_lue_du_corps(self):
        resp = auth(self.rh).post(
            self.BASE, self._payload(company=self.co_b.id), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Remuneration.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)


class RemunerationIsolationTests(TestCase):
    BASE = '/api/django/rh/remunerations/'

    def setUp(self):
        self.co_a = make_company('rem-iso-a', 'A')
        self.co_b = make_company('rem-iso-b', 'B')
        self.rh_b = make_user(self.co_b, 'rh-b', ['salaires_voir'])
        self.emp_a = DossierEmploye.objects.create(
            company=self.co_a, matricule='EMP001', nom='Kasri', prenom='Reda')
        Remuneration.objects.create(
            company=self.co_a, employe=self.emp_a, montant='8000',
            date_effet='2026-01-01')

    def test_isolation_entre_societes(self):
        resp = auth(self.rh_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)


class RemunerationHistoriqueTests(TestCase):
    BASE = '/api/django/rh/remunerations/'

    def setUp(self):
        self.co = make_company('rem-hist', 'H')
        self.rh = make_user(self.co, 'rh-hist', ['salaires_voir'])
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='EMP001', nom='Kasri', prenom='Reda')

    def test_historique_ordonne_du_plus_recent(self):
        # Trois lignes successives — nouvelle ligne supersede, ancienne conservée.
        Remuneration.objects.create(
            company=self.co, employe=self.emp, montant='6000',
            date_effet='2025-01-01')
        Remuneration.objects.create(
            company=self.co, employe=self.emp, montant='7000',
            date_effet='2025-07-01')
        Remuneration.objects.create(
            company=self.co, employe=self.emp, montant='8000',
            date_effet='2026-01-01')

        resp = auth(self.rh).get(f'{self.BASE}?employe={self.emp.id}')
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 3)
        dates = [r['date_effet'] for r in data]
        self.assertEqual(dates, ['2026-01-01', '2025-07-01', '2025-01-01'])
        # La ligne en vigueur est la première (la plus récente).
        self.assertEqual(data[0]['montant'], '8000.00')
