"""Tests XPLT10 — partage de dashboard (lien public tokenisé + mode TV +
partage interne granulaire).

Couvre :
  * un lien public affiche le dashboard sans login ;
  * révocation -> 404 (indistinct d'un jeton inconnu, pas de fuite) ;
  * expiration -> 410 ;
  * jamais de prix d'achat/liste nominative dans la réponse publique ;
  * un utilisateur non-partagé ne voit pas le dashboard interne d'autrui ;
  * un utilisateur partagé (direct ou par rôle) le voit ;
  * mode TV liste société-partagée + partages internes ;
  * isolation multi-tenant (aucune fuite cross-société) ;
  * VIA L'API : un dashboard (ou un utilisateur bénéficiaire) d'une AUTRE
    société est REFUSÉ par un 400 de validation, à la création comme à la mise
    à jour, sur les DEUX viewsets (lien public tokenisé + partage interne).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.dashboard_partage import (
    resolve_dashboard_partage_public, user_can_view_dashboard,
    PARTAGE_INTROUVABLE, PARTAGE_EXPIRE, PARTAGE_OK,
)
from core.models import Dashboard, DashboardPartageInterne, PartageDashboard

User = get_user_model()


class DashboardPartageBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='xplt10-co', defaults={'nom': 'XPLT10 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='xplt10-other', defaults={'nom': 'XPLT10 Other'})[0]
        self.owner = User.objects.create_user(
            username='xplt10_owner', password='x', company=self.company)
        self.viewer = User.objects.create_user(
            username='xplt10_viewer', password='x', company=self.company)
        self.dashboard = Dashboard.objects.create(
            company=self.company, owner=self.owner, titre='Mon dashboard',
            layout={'widgets': [{'type': 'kpi', 'valeur': 42}]})
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.owner)}')


class TestPublicLink(DashboardPartageBase):
    def test_public_link_shows_dashboard_without_login(self):
        partage = PartageDashboard.objects.create(
            company=self.company, dashboard=self.dashboard,
            created_by=self.owner)
        anon = APIClient()
        resp = anon.get(
            f'/api/django/core/dashboards-partages/public/{partage.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['titre'], 'Mon dashboard')
        self.assertEqual(resp.data['layout'], self.dashboard.layout)

    def test_revoked_link_returns_404(self):
        partage = PartageDashboard.objects.create(
            company=self.company, dashboard=self.dashboard,
            created_by=self.owner, actif=False)
        anon = APIClient()
        resp = anon.get(
            f'/api/django/core/dashboards-partages/public/{partage.token}/')
        self.assertEqual(resp.status_code, 404)

    def test_unknown_token_returns_404(self):
        anon = APIClient()
        resp = anon.get(
            '/api/django/core/dashboards-partages/public/does-not-exist/')
        self.assertEqual(resp.status_code, 404)

    def test_expired_link_returns_410(self):
        partage = PartageDashboard.objects.create(
            company=self.company, dashboard=self.dashboard,
            created_by=self.owner,
            expires_at=timezone.now() - datetime.timedelta(days=1))
        anon = APIClient()
        resp = anon.get(
            f'/api/django/core/dashboards-partages/public/{partage.token}/')
        self.assertEqual(resp.status_code, 410)

    def test_resolve_helper_statuses(self):
        partage = PartageDashboard.objects.create(
            company=self.company, dashboard=self.dashboard,
            created_by=self.owner)
        statut, obj = resolve_dashboard_partage_public(partage.token)
        self.assertEqual(statut, PARTAGE_OK)
        self.assertEqual(obj.id, partage.id)
        statut, obj = resolve_dashboard_partage_public('unknown-token')
        self.assertEqual(statut, PARTAGE_INTROUVABLE)
        partage.expires_at = timezone.now() - datetime.timedelta(hours=1)
        partage.save(update_fields=['expires_at'])
        statut, obj = resolve_dashboard_partage_public(partage.token)
        self.assertEqual(statut, PARTAGE_EXPIRE)

    def test_public_response_never_leaks_nominative_or_buy_price(self):
        """Le layout ne contient QUE l'agrégat déjà stocké — jamais une clé
        prix_achat/marge (aucune source de ce genre n'est ajoutée ici)."""
        partage = PartageDashboard.objects.create(
            company=self.company, dashboard=self.dashboard,
            created_by=self.owner)
        anon = APIClient()
        resp = anon.get(
            f'/api/django/core/dashboards-partages/public/{partage.token}/')
        self.assertNotIn('prix_achat', str(resp.data))
        self.assertNotIn('marge', str(resp.data).lower())

    def test_create_via_api_scoped_to_company(self):
        resp = self.api.post('/api/django/core/dashboards-partages/', {
            'dashboard': self.dashboard.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        partage = PartageDashboard.objects.get(id=resp.data['id'])
        self.assertEqual(partage.company_id, self.company.id)
        self.assertEqual(partage.created_by_id, self.owner.id)


class TestInternalSharing(DashboardPartageBase):
    def test_non_shared_user_cannot_view_personal_dashboard(self):
        self.assertFalse(
            user_can_view_dashboard(self.viewer, self.dashboard))

    def test_directly_shared_user_can_view(self):
        DashboardPartageInterne.objects.create(
            company=self.company, dashboard=self.dashboard,
            utilisateur=self.viewer,
            niveau=DashboardPartageInterne.Niveau.LECTURE)
        self.assertTrue(
            user_can_view_dashboard(self.viewer, self.dashboard))

    def test_role_shared_user_can_view(self):
        role_peer = User.objects.create_user(
            username='xplt10_role_peer', password='x', company=self.company,
            role_legacy='responsable')
        DashboardPartageInterne.objects.create(
            company=self.company, dashboard=self.dashboard,
            role='responsable', niveau=DashboardPartageInterne.Niveau.LECTURE)
        self.assertTrue(user_can_view_dashboard(role_peer, self.dashboard))

    def test_owner_always_sees_own_dashboard(self):
        self.assertTrue(user_can_view_dashboard(self.owner, self.dashboard))

    def test_company_wide_partage_flag_unaffected(self):
        """Le booléen `Dashboard.partage` (FG381) continue de fonctionner
        indépendamment du partage interne fin."""
        self.dashboard.partage = True
        self.dashboard.save(update_fields=['partage'])
        self.assertTrue(user_can_view_dashboard(self.viewer, self.dashboard))


class TestTvMode(DashboardPartageBase):
    def test_tv_mode_lists_company_wide_and_internally_shared(self):
        self.dashboard.partage = True
        self.dashboard.save(update_fields=['partage'])
        Dashboard.objects.create(
            company=self.company, owner=self.owner, titre='Perso non partagé',
            layout={})
        shared_personal = Dashboard.objects.create(
            company=self.company, owner=self.owner, titre='Perso partagé',
            layout={})
        DashboardPartageInterne.objects.create(
            company=self.company, dashboard=shared_personal,
            utilisateur=self.viewer)

        viewer_api = APIClient()
        viewer_api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.viewer)}')
        resp = viewer_api.get('/api/django/core/dashboards-tv/')
        self.assertEqual(resp.status_code, 200)
        titres = {d['titre'] for d in resp.data['dashboards']}
        self.assertIn('Mon dashboard', titres)  # partage=True
        self.assertIn('Perso partagé', titres)  # partage interne
        self.assertNotIn('Perso non partagé', titres)


class TestTenantIsolation(DashboardPartageBase):
    def test_other_company_dashboard_never_returned_via_partage_public(self):
        other_dash = Dashboard.objects.create(
            company=self.other_company, titre='Autre société', layout={})
        partage = PartageDashboard.objects.create(
            company=self.other_company, dashboard=other_dash)
        anon = APIClient()
        # Le jeton reste valide (résolution par jeton, pas par société) mais
        # ne fuit QUE les données de sa propre société — aucune fuite cross.
        resp = anon.get(
            f'/api/django/core/dashboards-partages/public/{partage.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['titre'], 'Autre société')
        # Le viewer de self.company ne peut PAS lister les partages d'une
        # autre société via l'API authentifiée (TenantMixin).
        resp2 = self.api.get('/api/django/core/dashboards-partages/')
        self.assertEqual(resp2.status_code, 200)
        ids = [p['id'] for p in resp2.data.get('results', resp2.data)]
        self.assertNotIn(partage.id, ids)


class TestCrossTenantCreationRefused(DashboardPartageBase):
    """Non-régression de la faille inter-sociétés : les cibles d'un partage
    (``dashboard``, ``utilisateur``) étaient des ``PrimaryKeyRelatedField``
    validés contre ``.objects.all()`` — toutes sociétés confondues. Forcer
    ``company`` côté vue ne suffisait pas : la ligne portait la société de
    l'auteur tout en pointant ailleurs. Tout passe ICI par l'API (jamais par
    une insertion directe en base) : c'est le chemin exploitable."""

    def _other_company_dashboard(self):
        return Dashboard.objects.create(
            company=self.other_company, titre='Confidentiel autre société',
            layout={'widgets': [{'type': 'kpi', 'valeur': 999}]})

    def test_public_partage_create_rejects_other_company_dashboard(self):
        """L'exploit : poster l'id d'un dashboard de la société B depuis un
        compte de la société A créait un lien PUBLIC (résolu par le seul
        jeton, sans login) servant titre/description/layout de B au monde
        entier. Doit être un 400 de validation explicite, pas un 500."""
        other_dash = self._other_company_dashboard()
        resp = self.api.post('/api/django/core/dashboards-partages/', {
            'dashboard': other_dash.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('dashboard', resp.data)
        self.assertFalse(
            PartageDashboard.objects.filter(dashboard=other_dash).exists())

    def test_public_partage_update_cannot_repoint_to_other_company(self):
        """Même faille par la porte de derrière : repointer un lien public
        LÉGITIME existant vers le dashboard d'une autre société."""
        other_dash = self._other_company_dashboard()
        partage = PartageDashboard.objects.create(
            company=self.company, dashboard=self.dashboard,
            created_by=self.owner)
        resp = self.api.patch(
            f'/api/django/core/dashboards-partages/{partage.id}/',
            {'dashboard': other_dash.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('dashboard', resp.data)
        partage.refresh_from_db()
        self.assertEqual(partage.dashboard_id, self.dashboard.id)

    def test_partage_interne_create_rejects_other_company_dashboard(self):
        other_dash = self._other_company_dashboard()
        resp = self.api.post(
            '/api/django/core/dashboards-partages-internes/', {
                'dashboard': other_dash.id,
                'utilisateur': self.viewer.id,
            }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('dashboard', resp.data)
        self.assertFalse(DashboardPartageInterne.objects.filter(
            dashboard=other_dash).exists())

    def test_partage_interne_create_rejects_other_company_user(self):
        """Le bénéficiaire aussi : une ligne ``company=A`` donnant à un
        utilisateur de B une prise sur un dashboard de A (la table est
        interrogée sans filtre de société par
        ``user_can_view_dashboard``)."""
        other_user = User.objects.create_user(
            username='xplt10_other_user', password='x',
            company=self.other_company)
        resp = self.api.post(
            '/api/django/core/dashboards-partages-internes/', {
                'dashboard': self.dashboard.id,
                'utilisateur': other_user.id,
            }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('utilisateur', resp.data)
        self.assertFalse(DashboardPartageInterne.objects.filter(
            utilisateur=other_user).exists())

    def test_partage_interne_same_company_still_created(self):
        """Contrôle positif : le cas légitime (tout dans la même société)
        reste un 201, société imposée côté serveur."""
        resp = self.api.post(
            '/api/django/core/dashboards-partages-internes/', {
                'dashboard': self.dashboard.id,
                'utilisateur': self.viewer.id,
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        partage = DashboardPartageInterne.objects.get(id=resp.data['id'])
        self.assertEqual(partage.company_id, self.company.id)
        self.assertEqual(partage.dashboard_id, self.dashboard.id)
        self.assertEqual(partage.utilisateur_id, self.viewer.id)
