"""
FG327 — Stock en consignation / emballages consignés.

Couvre :
  * création : société/`created_by` posés serveur ; désignation requise ;
  * un fournisseur d'une autre société rejeté ;
  * caution_totale dérivée ;
  * action retourner (pose `retourne_par`/`date_retour` + statut) ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg327_consignation -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import MaterielConsigne

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg327-co-{n}', defaults={'nom': nom or f'FG327 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg327-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_fournisseur(company, nom='Câbleries du Sud'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


class TestMaterielConsigne(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = make_fournisseur(self.company)

    def test_create_sets_company_server_side(self):
        resp = self.api.post(f'{BASE}/materiels-consignes/', {
            'designation': 'Touret 16mm²', 'type_materiel': 'touret',
            'fournisseur': self.fournisseur.id, 'quantite': 4,
            'caution_unitaire': '150.00', 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        mc = MaterielConsigne.objects.get(id=resp.data['id'])
        self.assertEqual(mc.company_id, self.company.id)
        self.assertEqual(mc.created_by_id, self.user.id)
        self.assertEqual(mc.statut, MaterielConsigne.Statut.DETENU)
        # caution_totale = 4 × 150
        self.assertEqual(str(resp.data['caution_totale']), '600.00')

    def test_blank_designation_rejected(self):
        resp = self.api.post(f'{BASE}/materiels-consignes/', {
            'designation': '  ', 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_fournisseur_other_company_rejected(self):
        other = make_company()
        f_other = make_fournisseur(other)
        resp = self.api.post(f'{BASE}/materiels-consignes/', {
            'designation': 'Palette', 'fournisseur': f_other.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_retourner(self):
        mc = MaterielConsigne.objects.create(
            company=self.company, designation='Palette EUR', quantite=10,
            caution_unitaire=20)
        resp = self.api.post(
            f'{BASE}/materiels-consignes/{mc.id}/retourner/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        mc.refresh_from_db()
        self.assertEqual(mc.statut, MaterielConsigne.Statut.RETOURNE)
        self.assertEqual(mc.retourne_par_id, self.user.id)
        self.assertIsNotNone(mc.date_retour)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/materiels-consignes/', {
            'designation': 'X', 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        MaterielConsigne.objects.create(
            company=self.company, designation='Touret', quantite=1)
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/materiels-consignes/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
