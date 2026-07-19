"""ODX13 — les partenaires/territoires commerciaux (FG234–237) sont relogés de
compta vers ``apps.crm`` (leur foyer Odoo naturel CRM/resellers), tables
physiques préservées (``compta_<model>``), nouvelles routes
``/api/django/crm/…`` + anciennes routes ``/api/django/compta/…`` conservées,
l'affectation par territoire se comporte à l'identique.

Run :
    python manage.py test apps.crm.tests_odx13_partenaires_split -v2
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


class TestODX13Relocation(TestCase):
    def test_models_live_in_crm_with_preserved_db_tables(self):
        from apps.crm.models import (
            Partenaire, SoumissionLeadPartenaire, CommissionPartenaire,
            TerritoireCommercial)
        from apps.compta.models import Partenaire as ComptaShimPartenaire
        # Le shim compta ré-exporte EXACTEMENT la même classe (ODX22 le retirera).
        self.assertIs(Partenaire, ComptaShimPartenaire)
        expected = {
            Partenaire: 'compta_partenaire',
            SoumissionLeadPartenaire: 'compta_soumissionleadpartenaire',
            CommissionPartenaire: 'compta_commissionpartenaire',
            TerritoireCommercial: 'compta_territoirecommercial',
        }
        for model, table in expected.items():
            self.assertEqual(model._meta.db_table, table)
            self.assertEqual(model._meta.app_label, 'crm')

    def test_crm_models_never_import_compta_models(self):
        """Garde-fou statique : ``apps.crm.models`` ne référence aucun
        ``apps.compta`` (le sens du shim va compta → crm, jamais l'inverse)."""
        import inspect

        from apps.crm import models as crm_models
        source = inspect.getsource(crm_models)
        self.assertNotIn('apps.compta', source)


class TestODX13Routes(TestCase):
    def setUp(self):
        self.company = make_company('odx13-co', 'ODX13 Co')
        self.user = make_user(self.company, 'odx13_resp')
        self.api = auth(self.user)

    def test_new_crm_route_creates_partenaire_scoped_serverside(self):
        r = self.api.post('/api/django/crm/partenaires/', {
            'nom': 'Apporteur Test', 'type_partenaire': 'apporteur',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        from apps.crm.models import Partenaire
        obj = Partenaire.objects.get(id=r.data['id'])
        self.assertEqual(obj.company_id, self.company.id)
        # Token généré côté serveur (surface AUTH inchangée) — jamais du corps.
        self.assertTrue(obj.token_acces)

    def test_legacy_compta_route_still_serves_same_data(self):
        from apps.crm.models import Partenaire
        obj = Partenaire.objects.create(
            company=self.company, nom='Sous-revendeur Historique',
            type_partenaire='sous_revendeur', token_acces='tok-odx13-legacy')
        r = self.api.get('/api/django/compta/partenaires/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(obj.id, ids_of(r))

    def test_territoire_served_on_single_compta_prefix(self):
        # WIR81 — le double montage ODX13 de TerritoireCommercial est retiré :
        # SEUL /api/django/compta/territoires-commerciaux/ répond ; l'ancienne
        # route /api/django/crm/… n'existe plus (404). Partenaires/soumissions/
        # commissions restent, eux, dual-montés (voir tests ci-dessus).
        from apps.crm.models import TerritoireCommercial
        TerritoireCommercial.objects.create(
            company=self.company, nom='Grand Casablanca',
            villes=['casablanca'], priorite=10, owner_user_id=self.user.id)
        r_legacy = self.api.get(
            '/api/django/compta/territoires-commerciaux/affecter/',
            {'ville': 'Casablanca'})
        self.assertEqual(r_legacy.status_code, 200, r_legacy.data)
        self.assertEqual(r_legacy.data['owner_user_id'], self.user.id)
        r_removed = self.api.get(
            '/api/django/crm/territoires-commerciaux/affecter/',
            {'ville': 'Casablanca'})
        self.assertEqual(r_removed.status_code, 404)

    def test_cross_company_partenaire_isolated_on_new_route(self):
        other = make_company('odx13-other', 'Autre Co ODX13')
        from apps.crm.models import Partenaire
        Partenaire.objects.create(
            company=other, nom='Partenaire Autre Société',
            token_acces='tok-odx13-other')
        r = self.api.get('/api/django/crm/partenaires/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids_of(r), [])
