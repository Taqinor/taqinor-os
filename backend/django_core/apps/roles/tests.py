"""Tests RBAC : sérialisation des utilisateurs d'un rôle + audit des rôles.

Couvre :
- l'API /roles/ renvoie la liste légère des utilisateurs portant chaque rôle
  (tâche RBAC « afficher les utilisateurs assignés »),
- create/update/delete d'un rôle écrit une ligne SettingsAuditLog
  section='roles' (tâche RBAC « journaliser à l'audit »),
- la société reste forcée côté serveur (multi-tenant),
- les protections existantes (rôle système / rôle assigné) ne sont pas
  affaiblies,
- VX234 : le diff structuré (permissions ajoutées/retirées) est journalisé
  même pour un échange net-neutre (compte de permissions inchangé).
"""
import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import SettingsAuditLog
from apps.roles.models import Role, ALL_PERMISSIONS

User = get_user_model()


class RolesRbacTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RBAC Co', slug='rbac-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True,
        )
        self.admin = User.objects.create_user(
            username='rbac_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # ── Liste des utilisateurs assignés ──────────────────────────────────
    def test_role_serializer_lists_assigned_users(self):
        role = Role.objects.create(
            company=self.company, nom='Comptable', permissions=['stock_voir'])
        User.objects.create_user(
            username='clara', password='x', role=role, company=self.company)
        User.objects.create_user(
            username='omar', password='x', role=role, company=self.company)
        resp = self.api.get(f'/api/django/roles/{role.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['users_count'], 2)
        usernames = sorted(u['username'] for u in resp.data['users'])
        self.assertEqual(usernames, ['clara', 'omar'])
        for u in resp.data['users']:
            self.assertIn('id', u)

    # ── Audit create / update / delete ───────────────────────────────────
    def test_create_role_writes_audit_row(self):
        resp = self.api.post(
            '/api/django/roles/',
            {'nom': 'Magasinier', 'permissions': ['stock_voir', 'stock_creer']},
            format='json')
        self.assertEqual(resp.status_code, 201)
        rows = SettingsAuditLog.objects.filter(
            company=self.company, section='roles')
        self.assertEqual(rows.count(), 1)
        row = rows.first()
        self.assertEqual(row.field_label, 'Rôle créé')
        self.assertEqual(row.user, self.admin)
        self.assertIn('Magasinier', row.new_value)

    def test_update_role_permissions_writes_audit_row(self):
        role = Role.objects.create(
            company=self.company, nom='Vendeur', permissions=['ventes_voir'])
        resp = self.api.patch(
            f'/api/django/roles/{role.id}/',
            {'permissions': ['ventes_voir', 'ventes_creer']},
            format='json')
        self.assertEqual(resp.status_code, 200)
        rows = SettingsAuditLog.objects.filter(
            company=self.company, section='roles', field_label='Rôle modifié')
        self.assertEqual(rows.count(), 1)

    def test_update_without_change_writes_no_audit_row(self):
        role = Role.objects.create(
            company=self.company, nom='Vendeur', permissions=['ventes_voir'])
        resp = self.api.patch(
            f'/api/django/roles/{role.id}/',
            {'permissions': ['ventes_voir']}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SettingsAuditLog.objects.filter(
            section='roles', field_label='Rôle modifié').exists())

    def test_delete_role_writes_audit_row(self):
        role = Role.objects.create(
            company=self.company, nom='Temp', permissions=['stock_voir'])
        resp = self.api.delete(f'/api/django/roles/{role.id}/')
        self.assertEqual(resp.status_code, 204)
        rows = SettingsAuditLog.objects.filter(
            company=self.company, section='roles', field_label='Rôle supprimé')
        self.assertEqual(rows.count(), 1)

    # ── Protections existantes préservées ────────────────────────────────
    def test_cannot_delete_system_role(self):
        resp = self.api.delete(f'/api/django/roles/{self.admin_role.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Role.objects.filter(id=self.admin_role.id).exists())

    def test_cannot_delete_assigned_role(self):
        role = Role.objects.create(
            company=self.company, nom='Assigné', permissions=['stock_voir'])
        User.objects.create_user(
            username='ria', password='x', role=role, company=self.company)
        resp = self.api.delete(f'/api/django/roles/{role.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Role.objects.filter(id=role.id).exists())

    # ── VX234 : diff structuré (échange net-neutre reste lisible) ────────
    def test_net_neutral_permission_swap_logs_added_and_removed(self):
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'crm_supprimer'])
        resp = self.api.patch(
            f'/api/django/roles/{role.id}/',
            {'permissions': ['crm_voir', 'ventes_export']}, format='json')
        self.assertEqual(resp.status_code, 200)
        row = SettingsAuditLog.objects.get(
            company=self.company, section='roles', field_label='Rôle modifié')
        new_value = json.loads(row.new_value)
        self.assertEqual(new_value['ajoutees'], ['ventes_export'])
        self.assertEqual(new_value['retirees'], ['crm_supprimer'])
        # Le compte total est net-neutre (2 → 2) : la preuve du bug corrigé
        # est que le diff distingue quand même les deux codes échangés.
        self.assertEqual(new_value['total'], 2)

    def test_create_role_audit_new_value_is_json_with_ajoutees(self):
        resp = self.api.post(
            '/api/django/roles/',
            {'nom': 'Magasinier2', 'permissions': ['stock_voir', 'stock_creer']},
            format='json')
        self.assertEqual(resp.status_code, 201)
        row = SettingsAuditLog.objects.get(
            company=self.company, section='roles', field_label='Rôle créé',
            field='role:Magasinier2')
        new_value = json.loads(row.new_value)
        self.assertEqual(
            sorted(new_value['ajoutees']), ['stock_creer', 'stock_voir'])
        self.assertEqual(new_value['retirees'], [])

    def test_company_is_forced_server_side_on_create(self):
        other = Company.objects.create(nom='Autre', slug='autre-co')
        resp = self.api.post(
            '/api/django/roles/',
            {'nom': 'Pirate', 'permissions': ['stock_voir'],
             'company': other.id},
            format='json')
        self.assertEqual(resp.status_code, 201)
        role = Role.objects.get(nom='Pirate')
        self.assertEqual(role.company, self.company)


class RolesEscalationGuardTest(TestCase):
    """ERR5 : un Responsable (palier promu, non-admin) ne peut pas s'auto-
    octroyer de permissions élevées ni modifier un rôle système, ce qui le
    promouvrait Administrateur."""

    def setUp(self):
        from apps.roles.models import (
            RESPONSABLE_PERMISSIONS, COMMERCIAL_PERMISSIONS,
        )
        self.company = Company.objects.create(nom='Esc Co', slug='esc-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        # Rôle (non système) porté par le Responsable, avec users_voir → palier
        # responsable mais SANS roles_gerer (donc non-admin).
        self.resp_role = Role.objects.create(
            company=self.company, nom='Resp perso',
            permissions=list(RESPONSABLE_PERMISSIONS), est_systeme=False)
        self.resp = User.objects.create_user(
            username='esc_resp', password='x', role=self.resp_role,
            role_legacy='responsable', company=self.company)
        self.admin = User.objects.create_user(
            username='esc_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)
        self.com_perms = list(COMMERCIAL_PERMISSIONS)

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_responsable_cannot_self_grant_roles_gerer(self):
        # Tente d'ajouter roles_gerer à son propre rôle → auto-escalade admin.
        new_perms = list(self.resp_role.permissions) + ['roles_gerer']
        resp = self._api(self.resp).patch(
            f'/api/django/roles/{self.resp_role.id}/',
            {'permissions': new_perms}, format='json')
        self.assertIn(resp.status_code, (400, 403), resp.data)
        self.resp_role.refresh_from_db()
        self.assertNotIn('roles_gerer', self.resp_role.permissions)

    def test_responsable_cannot_grant_elevated_on_new_role(self):
        resp = self._api(self.resp).post(
            '/api/django/roles/',
            {'nom': 'Pirate', 'permissions': ['crm_voir', 'prix_achat_voir']},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Role.objects.filter(
            company=self.company, nom='Pirate').exists())

    def test_responsable_cannot_modify_system_role(self):
        # Modifier un rôle système (ici Administrateur) est réservé à l'admin.
        resp = self._api(self.resp).patch(
            f'/api/django/roles/{self.admin_role.id}/',
            {'permissions': ['crm_voir']}, format='json')
        self.assertIn(resp.status_code, (400, 403), resp.data)
        self.admin_role.refresh_from_db()
        self.assertIn('roles_gerer', self.admin_role.permissions)

    def test_responsable_can_create_non_elevated_role(self):
        resp = self._api(self.resp).post(
            '/api/django/roles/',
            {'nom': 'Magasinier', 'permissions': ['stock_voir', 'stock_creer']},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_admin_can_grant_elevated_permission(self):
        resp = self._api(self.admin).post(
            '/api/django/roles/',
            {'nom': 'Compta', 'permissions': ['reporting_voir',
                                              'prix_achat_voir']},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        role = Role.objects.get(nom='Compta')
        self.assertIn('prix_achat_voir', role.permissions)

    def test_responsable_cannot_edit_own_role_permissions(self):
        # Même sans permission élevée, modifier les permissions de SON PROPRE
        # rôle est bloqué (auto-escalade défensive).
        resp = self._api(self.resp).patch(
            f'/api/django/roles/{self.resp_role.id}/',
            {'permissions': self.com_perms}, format='json')
        self.assertIn(resp.status_code, (400, 403), resp.data)


class RevueAccesTest(TestCase):
    """XPLT12 — Rapport de revue d'accès & comptes dormants.

    Couvre : le rapport liste les dormants avec leurs permissions effectives,
    le 2FA et les sessions actives ; le seuil ``dormant_days`` est paramétrable ;
    l'export CSV fonctionne ; un non-admin est refusé (403) ; l'isolation tenant
    (aucun compte d'une autre société ne fuit)."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from authentication.models import UserSession
        from apps.roles.models import RESPONSABLE_PERMISSIONS

        self.company = Company.objects.create(nom='Revue Co', slug='revue-co')
        self.other = Company.objects.create(nom='Autre Co', slug='autre-revue')

        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        # Rôle non-admin (aucun roles_gerer) pour tester le 403.
        self.resp_role = Role.objects.create(
            company=self.company, nom='Resp perso',
            permissions=list(RESPONSABLE_PERMISSIONS), est_systeme=False)

        now = timezone.now()
        self.admin = User.objects.create_user(
            username='revue_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)
        self.admin.last_login = now
        self.admin.save(update_fields=['last_login'])

        # Compte actif récent (non dormant), 2FA activé.
        self.recent = User.objects.create_user(
            username='recent_user', password='x', role=self.resp_role,
            company=self.company, totp_enabled=True)
        self.recent.last_login = now - timedelta(days=3)
        self.recent.save(update_fields=['last_login'])

        # Compte dormant (dernière connexion il y a 200 jours).
        self.dormant = User.objects.create_user(
            username='dormant_user', password='x', role=self.resp_role,
            company=self.company)
        self.dormant.last_login = now - timedelta(days=200)
        self.dormant.save(update_fields=['last_login'])

        # Compte jamais connecté → dormant.
        self.never = User.objects.create_user(
            username='never_user', password='x', role=self.resp_role,
            company=self.company)
        self.never.last_login = None
        self.never.save(update_fields=['last_login'])

        # Compte d'une AUTRE société : ne doit jamais apparaître.
        User.objects.create_user(
            username='foreign_user', password='x', company=self.other)

        # Deux sessions actives + une révoquée pour ``recent`` (compte 2).
        UserSession.objects.create(
            company=self.company, user=self.recent, jti='a', revoked=False)
        UserSession.objects.create(
            company=self.company, user=self.recent, jti='b', revoked=False)
        UserSession.objects.create(
            company=self.company, user=self.recent, jti='c', revoked=True)

        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _rows_by_username(self, data):
        return {r['username']: r for r in data['utilisateurs']}

    def test_report_lists_dormants_with_effective_permissions(self):
        resp = self.api.get('/api/django/roles/revue-acces/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = self._rows_by_username(resp.data)
        # L'utilisateur d'une autre société ne fuit pas (isolation tenant).
        self.assertNotIn('foreign_user', rows)
        self.assertEqual(resp.data['total'], 4)
        # Dormants : dormant_user (200 j) + never_user (jamais connecté).
        self.assertTrue(rows['dormant_user']['dormant'])
        self.assertTrue(rows['never_user']['dormant'])
        self.assertIsNone(rows['never_user']['jours_depuis_connexion'])
        self.assertFalse(rows['recent_user']['dormant'])
        self.assertEqual(resp.data['dormants'], 2)
        # Permissions effectives du dormant = celles de son rôle.
        self.assertIn('ventes_voir', rows['dormant_user']['permissions'])
        # 2FA + sessions actives (2 non révoquées, la révoquée exclue).
        self.assertTrue(rows['recent_user']['deux_fa'])
        self.assertEqual(rows['recent_user']['sessions_actives'], 2)
        self.assertFalse(rows['dormant_user']['deux_fa'])

    def test_dormant_days_threshold_is_configurable(self):
        # Seuil très bas (1 jour) → recent_user (3 j) devient dormant aussi.
        resp = self.api.get('/api/django/roles/revue-acces/?dormant_days=1')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['dormant_days'], 1)
        rows = self._rows_by_username(resp.data)
        self.assertTrue(rows['recent_user']['dormant'])

    def test_csv_export(self):
        resp = self.api.get('/api/django/roles/revue-acces/?format=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('username', body)
        self.assertIn('dormant_user', body)
        self.assertNotIn('foreign_user', body)

    def test_non_admin_forbidden(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.recent)}')
        resp = api.get('/api/django/roles/revue-acces/')
        self.assertEqual(resp.status_code, 403)


class AdsEnginePermissionsTest(TestCase):
    """ENG19 — Permissions adsengine_view/manage/approve et role mapping.

    Couvre:
    - Les trois permissions existent dans ALL_PERMISSIONS ;
    - init_roles mappe adsengine_view et adsengine_manage selon le pattern YRBAC3
      (toutes les roles canoniques sauf VIEWER pour manage; VIEWER inclus pour view) ;
    - adsengine_approve est réservé à DIRECTEUR, ADMIN, RESPONSABLE (ancien système)
      et COMMERCIAL_RESP/TECHNICIEN_RESP (responsable level), mais NOT à COMMERCIAL/
      TECHNICIEN/VIEWER.
    """

    def setUp(self):
        from apps.roles.models import (
            DIRECTEUR_PERMISSIONS, ADMIN_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
            COMMERCIAL_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS, TECHNICIEN_PERMISSIONS,
            VIEWER_PERMISSIONS, RESPONSABLE_PERMISSIONS, UTILISATEUR_PERMISSIONS,
        )
        self.company = Company.objects.create(nom='AdsEng Co', slug='adseng-co')

        # Créer les sept rôles canoniques avec leurs permissions par défaut.
        self.directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.commercial_resp = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=list(COMMERCIAL_RESP_PERMISSIONS), est_systeme=True)
        self.commercial = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        self.technicien_resp = Role.objects.create(
            company=self.company, nom='Technicien responsable',
            permissions=list(TECHNICIEN_RESP_PERMISSIONS), est_systeme=True)
        self.technicien = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS), est_systeme=True)
        self.viewer = Role.objects.create(
            company=self.company, nom='Viewer',
            permissions=list(VIEWER_PERMISSIONS), est_systeme=True)

        # Rôles légacy.
        self.responsable = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=list(RESPONSABLE_PERMISSIONS), est_systeme=True)
        self.utilisateur = Role.objects.create(
            company=self.company, nom='Utilisateur',
            permissions=list(UTILISATEUR_PERMISSIONS), est_systeme=True)

    def test_adsengine_permissions_in_all_permissions(self):
        """Les trois permissions existent dans ALL_PERMISSIONS."""
        self.assertIn('adsengine_view', ALL_PERMISSIONS)
        self.assertIn('adsengine_manage', ALL_PERMISSIONS)
        self.assertIn('adsengine_approve', ALL_PERMISSIONS)

    def test_adsengine_view_distribution(self):
        """adsengine_view est distribuée à tous les rôles."""
        roles_with_view = [
            self.directeur, self.admin, self.commercial_resp,
            self.commercial, self.technicien_resp, self.technicien,
            self.viewer, self.responsable, self.utilisateur,
        ]
        for role in roles_with_view:
            self.assertIn('adsengine_view', role.permissions,
                          f'{role.nom} doit avoir adsengine_view')

    def test_adsengine_manage_distribution(self):
        """adsengine_manage est distribuée à tous sauf VIEWER et UTILISATEUR."""
        roles_with_manage = [
            self.directeur, self.admin, self.commercial_resp,
            self.commercial, self.technicien_resp, self.technicien,
            self.responsable,
        ]
        for role in roles_with_manage:
            self.assertIn('adsengine_manage', role.permissions,
                          f'{role.nom} doit avoir adsengine_manage')

        roles_without_manage = [self.viewer, self.utilisateur]
        for role in roles_without_manage:
            self.assertNotIn('adsengine_manage', role.permissions,
                             f'{role.nom} ne doit NOT avoir adsengine_manage')

    def test_adsengine_approve_restricted(self):
        """adsengine_approve est réservé à DIRECTEUR, ADMIN, RESPONSABLE."""
        roles_with_approve = [
            self.directeur, self.admin, self.responsable,
        ]
        for role in roles_with_approve:
            self.assertIn('adsengine_approve', role.permissions,
                          f'{role.nom} doit avoir adsengine_approve')

        roles_without_approve = [
            self.commercial_resp, self.commercial,
            self.technicien_resp, self.technicien,
            self.viewer, self.utilisateur,
        ]
        for role in roles_without_approve:
            self.assertNotIn('adsengine_approve', role.permissions,
                             f'{role.nom} ne doit NOT avoir adsengine_approve')
