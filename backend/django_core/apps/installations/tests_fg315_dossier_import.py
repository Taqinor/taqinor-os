"""
FG315 — Suivi import / dédouanement.

Couvre :
  * création via l'API : référence (`IMP-`) + société + ``created_by`` posés
    CÔTÉ SERVEUR (jamais count()+1) ;
  * l'injection de ``company``/``reference``/``statut_douane`` est ignorée ;
  * un fournisseur d'une autre société est rejeté ;
  * l'action `avancer` (progression d'un cran, saut vers l'aval, refus de
    revenir en arrière) ;
  * le scope société et la barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg315_dossier_import -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DossierImport

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg315-co-{n}', defaults={'nom': nom or f'FG315 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg315-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_fournisseur(company, nom='China Solar'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


class TestDossierCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_server_side_ref(self):
        r = self.api.post(f'{BASE}/dossiers-import/', {
            'designation': 'Conteneur 540 panneaux 550W',
            'incoterm': 'cif', 'numero_conteneur': 'MSCU1234567',
        })
        self.assertEqual(r.status_code, 201, r.data)
        d = DossierImport.objects.get(id=r.data['id'])
        self.assertEqual(d.company_id, self.company.id)
        self.assertEqual(d.created_by_id, self.user.id)
        self.assertTrue(d.reference.startswith('IMP-'), d.reference)
        self.assertEqual(d.statut_douane, DossierImport.StatutDouane.COMMANDE)

    def test_injected_fields_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/dossiers-import/', {
            'company': autre.id, 'reference': 'IMP-HACK',
            'statut_douane': 'livre', 'designation': 'X',
        })
        self.assertEqual(r.status_code, 201, r.data)
        d = DossierImport.objects.get(id=r.data['id'])
        self.assertEqual(d.company_id, self.company.id)
        self.assertNotEqual(d.reference, 'IMP-HACK')
        self.assertEqual(d.statut_douane, DossierImport.StatutDouane.COMMANDE)

    def test_foreign_fournisseur_rejected(self):
        autre = make_company()
        f_o = make_fournisseur(autre)
        r = self.api.post(f'{BASE}/dossiers-import/', {
            'designation': 'X', 'fournisseur': f_o.id,
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_blank_designation_rejected(self):
        r = self.api.post(f'{BASE}/dossiers-import/', {'designation': '  '})
        self.assertEqual(r.status_code, 400, r.data)


class TestAvancer(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.d = DossierImport.objects.create(
            company=self.company, reference='IMP-T-1', designation='X',
            created_by=self.user)

    def test_avancer_one_step(self):
        r = self.api.post(f'{BASE}/dossiers-import/{self.d.id}/avancer/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut_douane'], 'expedie')

    def test_jump_forward(self):
        r = self.api.post(f'{BASE}/dossiers-import/{self.d.id}/avancer/',
                          {'statut_douane': 'dedouane'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut_douane'], 'dedouane')

    def test_cannot_go_backward(self):
        self.d.statut_douane = DossierImport.StatutDouane.DEDOUANE
        self.d.save(update_fields=['statut_douane'])
        r = self.api.post(f'{BASE}/dossiers-import/{self.d.id}/avancer/',
                          {'statut_douane': 'commande'})
        self.assertEqual(r.status_code, 400, r.data)

    def test_unknown_statut_rejected(self):
        r = self.api.post(f'{BASE}/dossiers-import/{self.d.id}/avancer/',
                          {'statut_douane': 'inconnu'})
        self.assertEqual(r.status_code, 400, r.data)


class TestScopeRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/dossiers-import/', {'designation': 'X'})
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        DossierImport.objects.create(
            company=other, reference='IMP-O-1', designation='Autre')
        DossierImport.objects.create(
            company=self.company, reference='IMP-M-1', designation='Mien')
        r = self.api.get(f'{BASE}/dossiers-import/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
