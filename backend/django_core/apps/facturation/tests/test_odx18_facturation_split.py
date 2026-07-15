"""ODX18 — App Facturation, étape 2 (vues/urls/recouvrement).

Les ViewSets/vues de facturation (Facture, Paiement, Avoir, FollowupLevel +
recouvrement) sont désormais servis SOUS DEUX préfixes : les nouvelles routes
``/api/django/facturation/…`` ET les routes historiques ``/api/django/ventes/…``
conservées à l'identique (mêmes classes, scoping société côté serveur, aucun
client cassé). Les PDFs facture restent le legacy (règle #4 — seul le devis
passe par /proposal).

Run :
    python manage.py test apps.facturation.tests.test_odx18_facturation_split -v2
"""
from decimal import Decimal

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


def make_client(company, email='odx18@example.com'):
    from crm.models import Client
    return Client.objects.create(
        company=company, nom='ODX18', prenom='Client', email=email,
        telephone='+212600000018', adresse='Casablanca')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data \
        else data
    return [x['id'] for x in rows]


class TestODX18ModelsShim(TestCase):
    def test_facturation_models_are_the_ventes_shim(self):
        # ODX17 a déplacé l'ÉTAT vers apps.facturation ; ventes garde un shim de
        # ré-export : la MÊME classe est visible des deux côtés.
        from apps.facturation.models import Facture, Paiement, Avoir
        from apps.ventes.models import (
            Facture as VF, Paiement as VP, Avoir as VA)
        self.assertIs(Facture, VF)
        self.assertIs(Paiement, VP)
        self.assertIs(Avoir, VA)
        # Tables physiques préservées (ventes_*), app_label = facturation.
        self.assertEqual(Facture._meta.db_table, 'ventes_facture')
        self.assertEqual(Facture._meta.app_label, 'facturation')


class TestODX18Routes(TestCase):
    def setUp(self):
        self.company = make_company('odx18-co', 'ODX18 Co')
        self.user = make_user(self.company, 'odx18_resp')
        self.client_obj = make_client(self.company)
        self.api = auth(self.user)

    def _facture(self, reference):
        from apps.facturation.models import Facture
        return Facture.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'))

    def test_new_facturation_route_lists_scoped(self):
        f = self._facture('FA-2026-0001')
        r = self.api.get('/api/django/facturation/factures/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(f.id, ids_of(r))

    def test_legacy_ventes_route_serves_same_data(self):
        f = self._facture('FA-2026-0002')
        r = self.api.get('/api/django/ventes/factures/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(f.id, ids_of(r))

    def test_recouvrement_dual_prefix_balance_agee(self):
        # La balance âgée est servie sous les deux préfixes à l'identique.
        r_new = self.api.get('/api/django/facturation/balance-agee/')
        r_old = self.api.get('/api/django/ventes/balance-agee/')
        self.assertEqual(r_new.status_code, 200, r_new.data)
        self.assertEqual(r_old.status_code, 200, r_old.data)

    def test_niveaux_relance_dual_prefix(self):
        r_new = self.api.get('/api/django/facturation/niveaux-relance/')
        r_old = self.api.get('/api/django/ventes/niveaux-relance/')
        self.assertEqual(r_new.status_code, 200, r_new.data)
        self.assertEqual(r_old.status_code, 200, r_old.data)

    def test_tenant_isolation_on_new_route(self):
        other = make_company('odx18-other', 'Autre Co')
        other_client = make_client(other, email='other18@example.com')
        from apps.facturation.models import Facture
        Facture.objects.create(
            company=other, reference='FA-X', client=other_client,
            statut=Facture.Statut.EMISE)
        r = self.api.get('/api/django/facturation/factures/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids_of(r), [])
