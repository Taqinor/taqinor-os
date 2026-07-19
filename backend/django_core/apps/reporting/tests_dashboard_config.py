"""FG96 — Tests de la config de tableau de bord par utilisateur / palier de rôle.

Couvre :
- create forces company server-side
- effective/ : per-user > palier > défaut Python
- isolation société (une société ne voit pas les configs d'une autre)
- pas de config stockée => retourne le jeu complet de cartes (aucune régression)
- validation (clés invalides, user+menu_tier ensemble, ni user ni menu_tier)
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import (
    DashboardConfig,
    ROLE_DEFAULT_CARDS,
    GLOBAL_DEFAULT_CARDS,
    ALL_DASHBOARD_CARDS,
)

User = get_user_model()

BASE_URL = '/api/django/reporting/dashboard-config/'
EFFECTIVE_URL = f'{BASE_URL}effective/'


def _auth(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _admin(company, username='admin_user'):
    return User.objects.create_user(
        username=username, password='x', role_legacy='admin',
        company=company)


def _normal(company, username='normal_user'):
    return User.objects.create_user(
        username=username, password='x', role_legacy='normal',
        company=company)


class DashboardConfigCreateTests(TestCase):
    """Company est toujours forcée côté serveur."""

    def setUp(self):
        self.company = Company.objects.create(nom='MainCo')
        self.other = Company.objects.create(nom='OtherCo')
        self.admin = _admin(self.company)
        self.api = _auth(self.admin)

    def test_create_per_user_forces_company_server_side(self):
        """company injectée dans le corps est ignorée."""
        payload = {
            'user': self.admin.pk,
            'menu_tier': '',
            'cards': ['kpis', 'ca_mensuel'],
            'company': self.other.pk,  # doit être ignoré
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        cfg = DashboardConfig.objects.get(pk=res.data['id'])
        self.assertEqual(cfg.company, self.company)
        self.assertEqual(cfg.user, self.admin)

    def test_create_role_default_config(self):
        """Créer une config de palier pour 'admin'."""
        payload = {
            'user': None,
            'menu_tier': 'admin',
            'cards': ['kpis', 'ca_mensuel', 'top_produits'],
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        cfg = DashboardConfig.objects.get(pk=res.data['id'])
        self.assertEqual(cfg.company, self.company)
        self.assertIsNone(cfg.user)
        self.assertEqual(cfg.menu_tier, 'admin')
        self.assertEqual(cfg.cards, ['kpis', 'ca_mensuel', 'top_produits'])

    def test_invalid_card_key_rejected(self):
        payload = {
            'user': self.admin.pk,
            'menu_tier': '',
            'cards': ['kpis', 'CARTE_INEXISTANTE'],
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 400)

    def test_integrite_card_key_is_registered_and_valid(self):
        """WIR22 — la clé 'integrite' (badge du contrôle d'intégrité
        inter-documents) est enregistrée dans ALL_DASHBOARD_CARDS et acceptée
        par la validation serveur des clés de carte."""
        self.assertIn('integrite', ALL_DASHBOARD_CARDS)
        payload = {
            'user': self.admin.pk,
            'menu_tier': '',
            'cards': ['kpis', 'integrite'],
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_kpi_federes_card_key_is_registered_and_valid(self):
        """WIR100 — la clé 'kpi_federes' (tuiles KPI agrégées des modules
        actifs, ARC40) est enregistrée dans ALL_DASHBOARD_CARDS et acceptée
        par la validation serveur des clés de carte."""
        self.assertIn('kpi_federes', ALL_DASHBOARD_CARDS)
        payload = {
            'user': self.admin.pk,
            'menu_tier': '',
            'cards': ['kpis', 'kpi_federes'],
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_user_and_menu_tier_together_rejected(self):
        payload = {
            'user': self.admin.pk,
            'menu_tier': 'admin',
            'cards': ['kpis'],
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 400)

    def test_neither_user_nor_menu_tier_rejected(self):
        payload = {
            'user': None,
            'menu_tier': '',
            'cards': ['kpis'],
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 400)

    def test_empty_cards_list_is_valid(self):
        """Une liste vide = toutes les cartes désactivées (cas valide)."""
        payload = {
            'user': self.admin.pk,
            'menu_tier': '',
            'cards': [],
        }
        res = self.api.post(BASE_URL, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        cfg = DashboardConfig.objects.get(pk=res.data['id'])
        self.assertEqual(cfg.cards, [])


class DashboardConfigEffectiveTests(TestCase):
    """Résolution de la config effective : per-user > palier > défaut Python."""

    def setUp(self):
        self.company = Company.objects.create(nom='EffCo')
        self.other = Company.objects.create(nom='OtherCo')
        self.admin = _admin(self.company, 'eff_admin')
        self.normal = _normal(self.company, 'eff_normal')
        self.api_admin = _auth(self.admin)
        self.api_normal = _auth(self.normal)

    def test_no_config_returns_python_default_admin(self):
        """Aucune config en base => retourne ROLE_DEFAULT_CARDS['admin'] (= ALL_DASHBOARD_CARDS)."""
        res = self.api_admin.get(EFFECTIVE_URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['source'], 'python_default')
        self.assertEqual(res.data['cards'], ROLE_DEFAULT_CARDS.get('admin', GLOBAL_DEFAULT_CARDS))

    def test_no_config_returns_python_default_normal(self):
        """Aucune config en base => retourne ROLE_DEFAULT_CARDS['normal'] pour un user normal."""
        res = self.api_normal.get(EFFECTIVE_URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['source'], 'python_default')
        expected = ROLE_DEFAULT_CARDS.get('normal', GLOBAL_DEFAULT_CARDS)
        self.assertEqual(res.data['cards'], expected)

    def test_role_default_overrides_python_default(self):
        """Config de palier stockée en base override le défaut Python."""
        custom_cards = ['kpis', 'ca_mensuel']
        DashboardConfig.objects.create(
            company=self.company,
            user=None,
            menu_tier='admin',
            cards=custom_cards,
        )
        res = self.api_admin.get(EFFECTIVE_URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['source'], 'role_default')
        self.assertEqual(res.data['cards'], custom_cards)

    def test_per_user_overrides_role_default(self):
        """Config per-user prend la priorité sur la config de palier."""
        role_cards = ['kpis', 'ca_mensuel']
        user_cards = ['kpis']
        DashboardConfig.objects.create(
            company=self.company,
            user=None,
            menu_tier='admin',
            cards=role_cards,
        )
        DashboardConfig.objects.create(
            company=self.company,
            user=self.admin,
            menu_tier='',
            cards=user_cards,
        )
        res = self.api_admin.get(EFFECTIVE_URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['source'], 'per_user')
        self.assertEqual(res.data['cards'], user_cards)

    def test_effective_is_company_scoped(self):
        """La config d'une autre société n'affecte pas la réponse."""
        other_admin = _admin(self.other, 'other_admin_eff')
        other_cards = ['kpis']  # config stockée pour l'autre société
        DashboardConfig.objects.create(
            company=self.other,
            user=other_admin,
            menu_tier='',
            cards=other_cards,
        )
        # L'admin de this.company ne doit pas voir la config de other.
        res = self.api_admin.get(EFFECTIVE_URL)
        self.assertEqual(res.status_code, 200, res.data)
        # Source = python_default (pas de config pour this.company)
        self.assertEqual(res.data['source'], 'python_default')


class DashboardConfigListScopeTests(TestCase):
    """Le listing CRUD est borné à la société de l'utilisateur."""

    def setUp(self):
        self.company = Company.objects.create(nom='ListCo')
        self.other = Company.objects.create(nom='OtherListCo')
        self.admin = _admin(self.company, 'list_admin')
        self.other_admin = _admin(self.other, 'other_list_admin')
        self.api = _auth(self.admin)

    def test_list_is_company_scoped(self):
        DashboardConfig.objects.create(
            company=self.company, user=self.admin, menu_tier='', cards=['kpis'])
        DashboardConfig.objects.create(
            company=self.other, user=self.other_admin, menu_tier='',
            cards=['ca_mensuel'])
        res = self.api.get(BASE_URL)
        self.assertEqual(res.status_code, 200, res.data)
        results = res.data.get('results', res.data)
        ids = [r['id'] for r in results]
        # Seul l'enregistrement de self.company doit apparaître.
        self.assertEqual(len(ids), 1)
        cfg = DashboardConfig.objects.get(pk=ids[0])
        self.assertEqual(cfg.company, self.company)

    def test_cannot_fetch_other_company_config(self):
        other_cfg = DashboardConfig.objects.create(
            company=self.other, user=self.other_admin, menu_tier='',
            cards=['kpis'])
        res = self.api.get(f'{BASE_URL}{other_cfg.pk}/')
        self.assertEqual(res.status_code, 404)
