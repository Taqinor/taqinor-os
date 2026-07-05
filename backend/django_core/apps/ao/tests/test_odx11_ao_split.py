"""ODX11 — les appels d'offres (FG222–227) sont relogés de compta vers
``apps.ao``, tables physiques préservées (``compta_<model>``), nouvelles routes
``/api/django/ao/…`` + anciennes routes ``/api/django/compta/…`` conservées,
scoping société côté serveur.

Run :
    python manage.py test apps.ao.tests.test_odx11_ao_split -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [x['id'] for x in rows]


class TestODX11Relocation(TestCase):
    def test_models_live_in_ao_with_preserved_db_tables(self):
        from apps.ao.models import (
            AppelOffre, BordereauPrix, LigneBordereau, CautionSoumission,
            DossierSoumission, PieceSoumission, EcheanceAO, ResultatAO)
        from apps.compta.models import AppelOffre as ComptaShimAppelOffre
        # Le shim compta ré-exporte EXACTEMENT la même classe (ODX22 le retirera).
        self.assertIs(AppelOffre, ComptaShimAppelOffre)
        expected = {
            AppelOffre: 'compta_appeloffre',
            BordereauPrix: 'compta_bordereauprix',
            LigneBordereau: 'compta_lignebordereau',
            CautionSoumission: 'compta_cautionsoumission',
            DossierSoumission: 'compta_dossiersoumission',
            PieceSoumission: 'compta_piecesoumission',
            EcheanceAO: 'compta_echeanceao',
            ResultatAO: 'compta_resultatao',
        }
        for model, table in expected.items():
            self.assertEqual(model._meta.db_table, table)
            self.assertEqual(model._meta.app_label, 'ao')


class TestODX11Routes(TestCase):
    def setUp(self):
        self.company = make_company('odx11-co', 'ODX11 Co')
        self.user = make_user(self.company, 'odx11_resp')
        self.api = auth(self.user)

    def test_new_ao_route_creates_scoped(self):
        r = self.api.post('/api/django/ao/appels-offres/', {
            'reference': 'AO-2026-01', 'objet': 'Centrale PV 500 kWc',
            'type_marche': 'public',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        from apps.ao.models import AppelOffre
        obj = AppelOffre.objects.get(id=r.data['id'])
        self.assertEqual(obj.company_id, self.company.id)

    def test_legacy_compta_route_still_serves_same_data(self):
        from apps.ao.models import AppelOffre
        obj = AppelOffre.objects.create(
            company=self.company, reference='AO-2026-02',
            objet='Pompage agricole')
        r = self.api.get('/api/django/compta/appels-offres/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(obj.id, ids_of(r))

    def test_tenant_isolation_on_new_route(self):
        other = make_company('odx11-other', 'Autre Co')
        from apps.ao.models import AppelOffre
        AppelOffre.objects.create(
            company=other, reference='AO-X', objet='Autre société')
        r = self.api.get('/api/django/ao/appels-offres/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids_of(r), [])
