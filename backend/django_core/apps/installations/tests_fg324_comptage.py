"""
FG324 — Sessions de comptage tournant (cycle count ABC).

Couvre :
  * création d'une session : référence (`CYC-`) + société + `created_by` serveur ;
  * un emplacement d'une autre société rejeté ;
  * `ajouter-ligne` snapshote la quantité théorique serveur depuis le stock ;
  * un produit d'une autre société rejeté à l'ajout ;
  * écart dérivé (comptée − théorique) ;
  * cycle démarrer/terminer ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg324_comptage -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import SessionComptage, ComptageLigne

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg324-co-{n}', defaults={'nom': nom or f'FG324 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg324-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Panneau 550W', stock=42):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0,
        quantite_stock=stock)


class TestSessionComptage(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.emp = make_emplacement(self.company)
        self.produit = make_produit(self.company, stock=42)

    def test_create_sets_reference_company_server_side(self):
        resp = self.api.post(f'{BASE}/sessions-comptage/', {
            'intitule': 'Comptage A janvier', 'emplacement': self.emp.id,
            'classe_abc': 'A', 'company': 999, 'reference': 'HACK',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        s = SessionComptage.objects.get(id=resp.data['id'])
        self.assertEqual(s.company_id, self.company.id)
        self.assertEqual(s.created_by_id, self.user.id)
        self.assertTrue(s.reference.startswith('CYC-'))
        self.assertEqual(s.statut, SessionComptage.Statut.PLANIFIE)

    def test_emplacement_other_company_rejected(self):
        other = make_company()
        emp_other = make_emplacement(other)
        resp = self.api.post(f'{BASE}/sessions-comptage/', {
            'emplacement': emp_other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_ajouter_ligne_snapshots_theoretical(self):
        session = SessionComptage.objects.create(
            company=self.company, reference='CYC-X')
        resp = self.api.post(
            f'{BASE}/sessions-comptage/{session.id}/ajouter-ligne/',
            {'produit': self.produit.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ligne = ComptageLigne.objects.get(id=resp.data['id'])
        self.assertEqual(ligne.quantite_theorique, 42)

    def test_ajouter_ligne_other_company_produit_rejected(self):
        other = make_company()
        p_other = make_produit(other)
        session = SessionComptage.objects.create(
            company=self.company, reference='CYC-Y')
        resp = self.api.post(
            f'{BASE}/sessions-comptage/{session.id}/ajouter-ligne/',
            {'produit': p_other.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_ecart_derived(self):
        session = SessionComptage.objects.create(
            company=self.company, reference='CYC-Z')
        ligne = ComptageLigne.objects.create(
            session=session, produit=self.produit, quantite_theorique=42)
        resp = self.api.patch(
            f'{BASE}/comptage-lignes/{ligne.id}/',
            {'quantite_comptee': 40, 'compte': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['ecart'], -2)

    def test_cycle_demarrer_terminer(self):
        session = SessionComptage.objects.create(
            company=self.company, reference='CYC-W')
        r1 = self.api.post(
            f'{BASE}/sessions-comptage/{session.id}/demarrer/', {},
            format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        session.refresh_from_db()
        self.assertEqual(session.statut, SessionComptage.Statut.EN_COURS)
        r2 = self.api.post(
            f'{BASE}/sessions-comptage/{session.id}/terminer/', {},
            format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        session.refresh_from_db()
        self.assertEqual(session.statut, SessionComptage.Statut.TERMINE)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/sessions-comptage/', {
            'intitule': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        SessionComptage.objects.create(
            company=self.company, reference='CYC-S')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/sessions-comptage/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
