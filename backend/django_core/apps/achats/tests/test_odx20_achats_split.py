"""ODX20 — App Achats, étape 2 (vues/urls/flux stock).

Les ViewSets achats fournisseurs (BCF, réceptions, factures fournisseur,
paiements, retours, prix fournisseur) sont désormais servis SOUS DEUX préfixes :
les nouvelles routes ``/api/django/achats/…`` ET les routes historiques
``/api/django/stock/…`` conservées à l'identique (mêmes classes, scoping société
côté serveur, aucun client cassé). Les mouvements de stock à la réception/au
retour passent par ``apps.stock.services`` (jamais d'import direct des modèles
stock).

Run :
    python manage.py test apps.achats.tests.test_odx20_achats_split -v2
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


def make_fournisseur(company, nom='ODX20 Fournisseur'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data \
        else data
    return [x['id'] for x in rows]


class TestODX20ModelsShim(TestCase):
    def test_achats_models_are_the_stock_shim(self):
        # ODX19 a déplacé l'ÉTAT vers apps.achats ; stock garde un shim de
        # ré-export : la MÊME classe est visible des deux côtés.
        from apps.achats.models import (
            BonCommandeFournisseur, ReceptionFournisseur, FactureFournisseur)
        from apps.stock.models import (
            BonCommandeFournisseur as SB,
            ReceptionFournisseur as SR,
            FactureFournisseur as SF)
        self.assertIs(BonCommandeFournisseur, SB)
        self.assertIs(ReceptionFournisseur, SR)
        self.assertIs(FactureFournisseur, SF)
        # Tables physiques préservées (stock_*), app_label = achats.
        self.assertEqual(
            BonCommandeFournisseur._meta.db_table,
            'stock_boncommandefournisseur')
        self.assertEqual(
            BonCommandeFournisseur._meta.app_label, 'achats')


class TestODX20Routes(TestCase):
    def setUp(self):
        self.company = make_company('odx20-co', 'ODX20 Co')
        self.user = make_user(self.company, 'odx20_resp')
        self.fournisseur = make_fournisseur(self.company)
        self.api = auth(self.user)

    def _bcf(self, reference):
        from apps.achats.models import BonCommandeFournisseur
        return BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur)

    def test_new_achats_route_lists_scoped(self):
        bcf = self._bcf('BCF-2026-0001')
        r = self.api.get('/api/django/achats/bons-commande-fournisseur/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(bcf.id, ids_of(r))

    def test_legacy_stock_route_serves_same_data(self):
        bcf = self._bcf('BCF-2026-0002')
        r = self.api.get('/api/django/stock/bons-commande-fournisseur/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(bcf.id, ids_of(r))

    def test_prix_fournisseurs_dual_prefix(self):
        r_new = self.api.get('/api/django/achats/prix-fournisseurs/')
        r_old = self.api.get('/api/django/stock/prix-fournisseurs/')
        self.assertEqual(r_new.status_code, 200, r_new.data)
        self.assertEqual(r_old.status_code, 200, r_old.data)

    def test_tenant_isolation_on_new_route(self):
        other = make_company('odx20-other', 'Autre Co')
        other_f = make_fournisseur(other, nom='Autre Fournisseur')
        from apps.achats.models import BonCommandeFournisseur
        BonCommandeFournisseur.objects.create(
            company=other, reference='BCF-X', fournisseur=other_f)
        r = self.api.get('/api/django/achats/bons-commande-fournisseur/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids_of(r), [])
