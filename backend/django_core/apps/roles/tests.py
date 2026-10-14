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
from apps.roles.models import Role
from apps.roles.permissions_registre import ALL_PERMISSIONS

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

    def test_role_nom_numerique_refuse_400(self):
        """ENF11 — ``nom`` doit être une chaîne JSON (pas de coercition)."""
        resp = self.api.post(
            '/api/django/roles/', {'nom': 5, 'permissions': []}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('nom', resp.data)

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

    def test_permissions_liste_de_textes_sinon_400(self):
        # ENF11 — `permissions` null / objet / texte / code non texte : 400
        # qui nomme le champ ; le rôle n'est pas modifié.
        role = Role.objects.create(
            company=self.company, nom='Strict', permissions=['stock_voir'])
        url = f'/api/django/roles/{role.id}/'
        for mauvais in (None, {}, 'stock_voir', [1], [None]):
            for methode in (self.api.patch, self.api.put):
                resp = methode(url, {'nom': 'Strict', 'permissions': mauvais},
                               format='json')
                self.assertEqual(resp.status_code, 400, (mauvais, resp.data))
                self.assertIn('permissions', resp.data)
        role.refresh_from_db()
        self.assertEqual(role.permissions, ['stock_voir'])

    def test_entites_visibles_liste_sinon_400(self):
        # ENF11 (api-fuzz) — `entites_visibles` est une liste d'identifiants :
        # `{}` / texte / nombre = 400 (DRF lisait `{}` comme « liste vide »).
        role = Role.objects.create(
            company=self.company, nom='Perimetre', permissions=['stock_voir'])
        url = f'/api/django/roles/{role.id}/'
        for mauvais in ({}, 'x', 3):
            resp = self.api.patch(
                url, {'entites_visibles': mauvais}, format='json')
            self.assertEqual(resp.status_code, 400, (mauvais, resp.data))
            self.assertIn('entites_visibles', resp.data)
        resp = self.api.patch(url, {'entites_visibles': []}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

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
        from apps.roles.permissions_registre import (
            RESPONSABLE_PERMISSIONS,
            COMMERCIAL_PERMISSIONS,
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
        from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS

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

    def test_erreur_revue_acces_reste_en_json(self):
        """ENF11 — ``dormant_days`` illisible ou négatif = 400, et une erreur
        n'est JAMAIS rendue en ``text/csv`` (même avec ``?format=csv``)."""
        for qs in ('dormant_days=abc', 'format=csv&dormant_days=-1'):
            resp = self.api.get(f'/api/django/roles/revue-acces/?{qs}')
            self.assertEqual(resp.status_code, 400, qs)
            self.assertIn('application/json', resp['Content-Type'], qs)
            self.assertIn('dormant_days', resp.json(), qs)

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
        from apps.roles.permissions_registre import (
            DIRECTEUR_PERMISSIONS,
            ADMIN_PERMISSIONS,
            COMMERCIAL_RESP_PERMISSIONS,
            COMMERCIAL_PERMISSIONS,
            TECHNICIEN_RESP_PERMISSIONS,
            TECHNICIEN_PERMISSIONS,
            VIEWER_PERMISSIONS,
            RESPONSABLE_PERMISSIONS,
            UTILISATEUR_PERMISSIONS,
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


class CodesGrilleAppliquesTests(TestCase):
    """ASEC50 / D-ASEC-4 (C-ASEC-015) — les codes d'export, de suppression et
    de réaffectation de la grille sont appliqués côté serveur
    (``apps.roles.permissions.DroitDeLaGrille``).

    Pour chaque code × endpoint : deux rôles personnalisés IDENTIQUES sauf la
    présence du code. Sans le code → 403 ``droit_manquant`` qui nomme le code,
    sans effet (CLAUSE PERSISTANCE : l'objet relu est présent / inchangé) ;
    avec → le comportement d'avant. Test-du-test : retirer la classe d'un
    endpoint (p. ex. l'export clients) fait échouer son cas « sans »."""

    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Client, Lead
        from apps.installations.models import Installation
        from apps.sav.models import EquipeMaintenance
        cls.company = Company.objects.create(
            nom='ASEC50 Codes', slug='asec50-codes-grille')
        cls.collegue = User.objects.create_user(
            username='asec50-collegue', password='x', company=cls.company,
            role_legacy='responsable')
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='ASEC50')
        cls.Lead = Lead
        cls.equipe_a = EquipeMaintenance.objects.create(
            company=cls.company, nom='Équipe A')
        cls.equipe_b = EquipeMaintenance.objects.create(
            company=cls.company, nom='Équipe B')
        cls.chantier = Installation.objects.create(
            company=cls.company, reference='CH-ASEC50', client=cls.client_obj)

    def setUp(self):
        self._n = 0

    def _api(self, base, code, avec):
        self._n += 1
        role = Role.objects.create(
            company=self.company, nom=f'ASEC50 {code} {self._n}',
            permissions=list(base) + ([code] if avec else []))
        user = User.objects.create_user(
            username=f'asec50-{code}-{self._n}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _paire(self, base, code):
        return self._api(base, code, False), self._api(base, code, True)

    def _refus(self, resp, code):
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(resp.data.get('code'), 'droit_manquant', resp.data)
        self.assertIn(code, str(resp.data.get('detail')))

    def _lead(self, owner=None):
        return self.Lead.objects.create(
            company=self.company, nom='Lead ASEC50', owner=owner)

    # ── exports ─────────────────────────────────────────────────────────
    def test_crm_export_leads_et_clients(self):
        lead = self._lead()
        for url, corps in (('/api/django/crm/leads/export-xlsx/',
                            {'ids': [lead.pk]}),
                           ('/api/django/crm/clients/export-xlsx/', {})):
            with self.subTest(url=url):
                sans, avec = self._paire(['crm_voir'], 'crm_export')
                self._refus(sans.post(url, corps, format='json'), 'crm_export')
                self.assertEqual(
                    avec.post(url, corps, format='json').status_code, 200)

    def test_crm_export_donnees_d_un_client(self):
        url = f'/api/django/crm/clients/{self.client_obj.pk}/data-export/'
        sans, avec = self._paire(['crm_voir', 'crm_modifier'], 'crm_export')
        self._refus(sans.get(url), 'crm_export')
        resp = avec.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['identite']['id'], self.client_obj.pk)

    def test_ventes_export_dgi_et_reporting_export(self):
        # Le droit est tranché AVANT la lecture de l'objet : sans le code →
        # 403 ; avec → la vue s'exécute (objet absent → 404, comme avant).
        for base, code, url in (
                (['ventes_voir', 'ventes_modifier'], 'ventes_export',
                 '/api/django/ventes/factures/999999/dgi-export/'),
                (['reporting_voir'], 'reporting_export',
                 '/api/django/reporting/rapport-definitions/999999/export/')):
            with self.subTest(code=code):
                sans, avec = self._paire(base, code)
                self._refus(sans.get(url), code)
                self.assertEqual(avec.get(url).status_code, 404)

    # ── suppressions ────────────────────────────────────────────────────
    def test_crm_supprimer_lead_client_et_masse(self):
        from apps.crm.models import Client
        base = ['crm_voir', 'crm_modifier', 'roles_gerer']
        lead = self._lead()
        sans, avec = self._paire(base, 'crm_supprimer')
        self._refus(sans.delete(f'/api/django/crm/leads/{lead.pk}/'),
                    'crm_supprimer')
        self.assertTrue(self.Lead.objects.filter(pk=lead.pk).exists())
        corps = {'action': 'delete', 'ids': [lead.pk]}
        self._refus(sans.post('/api/django/crm/leads/bulk/', corps,
                              format='json'), 'crm_supprimer')
        self.assertTrue(self.Lead.objects.filter(pk=lead.pk).exists())
        self.assertEqual(
            avec.delete(f'/api/django/crm/leads/{lead.pk}/').status_code, 200)
        self.assertFalse(self.Lead.objects.filter(pk=lead.pk).exists())

        client = Client.objects.create(company=self.company, nom='À effacer')
        url = f'/api/django/crm/clients/{client.pk}/'
        self._refus(sans.delete(url), 'crm_supprimer')
        self.assertTrue(Client.objects.filter(pk=client.pk).exists())
        self.assertEqual(avec.delete(url).status_code, 204)

    def test_ventes_supprimer_devis(self):
        from decimal import Decimal
        from apps.ventes.models import Devis
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASEC50-1',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), created_by=self.collegue)
        url = f'/api/django/ventes/devis/{devis.pk}/'
        sans, avec = self._paire(['ventes_voir', 'roles_gerer'],
                                 'ventes_supprimer')
        self._refus(sans.delete(url), 'ventes_supprimer')
        self.assertTrue(Devis.objects.filter(pk=devis.pk).exists())
        self.assertEqual(avec.delete(url).status_code, 204)

    # ── réaffectations ──────────────────────────────────────────────────
    def test_crm_reassign_masse_et_patch_owner(self):
        lead = self._lead()
        sans, avec = self._paire(['crm_voir', 'crm_modifier'], 'crm_reassign')
        corps = {'action': 'reassign', 'ids': [lead.pk],
                 'owner': self.collegue.pk}
        self._refus(sans.post('/api/django/crm/leads/bulk/', corps,
                              format='json'), 'crm_reassign')
        url = f'/api/django/crm/leads/{lead.pk}/'
        self._refus(sans.patch(url, {'owner': self.collegue.pk},
                               format='json'), 'crm_reassign')
        lead.refresh_from_db()
        self.assertIsNone(lead.owner_id)
        # Renvoyer la valeur COURANTE n'est pas une réaffectation.
        self.assertEqual(sans.patch(url, {'owner': None, 'nom': 'Renommé'},
                                    format='json').status_code, 200)
        self.assertEqual(avec.patch(url, {'owner': self.collegue.pk},
                                    format='json').status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.collegue.pk)

    def test_sav_reassign_equipe(self):
        from apps.sav.models import Ticket
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ASEC50-1',
            client=self.client_obj, equipe=self.equipe_a,
            statut=Ticket.Statut.NOUVEAU)
        sans, avec = self._paire(['sav_voir', 'sav_gerer'], 'sav_reassign')
        url = f'/api/django/sav/tickets/{ticket.pk}/'
        self._refus(sans.post(f'{url}reaffecter-equipe/',
                              {'equipe': self.equipe_b.pk}, format='json'),
                    'sav_reassign')
        self._refus(sans.patch(url, {'equipe': self.equipe_b.pk},
                               format='json'), 'sav_reassign')
        ticket.refresh_from_db()
        self.assertEqual(ticket.equipe_id, self.equipe_a.pk)
        self.assertEqual(avec.post(f'{url}reaffecter-equipe/',
                                   {'equipe': self.equipe_b.pk},
                                   format='json').status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.equipe_id, self.equipe_b.pk)

    def test_technicien_assign_intervention(self):
        from apps.installations.models import Intervention
        interv = Intervention.objects.create(
            company=self.company, installation=self.chantier)
        base = ['installation_voir', 'installation_gerer']
        sans, avec = self._paire(base, 'technicien_assign')
        url = f'/api/django/installations/interventions/{interv.pk}/'
        self._refus(sans.patch(url, {'technicien': self.collegue.pk},
                               format='json'), 'technicien_assign')
        interv.refresh_from_db()
        self.assertIsNone(interv.technicien_id)
        masse = '/api/django/installations/interventions/replanifier-en-masse/'
        corps = {'jour': '2026-10-15', 'technicien': self.collegue.pk,
                 'simuler': True}
        self._refus(sans.post(masse, corps, format='json'),
                    'technicien_assign')
        self.assertNotEqual(
            avec.post(masse, corps, format='json').status_code, 403)
        self.assertEqual(avec.patch(url, {'technicien': self.collegue.pk},
                                    format='json').status_code, 200)
        interv.refresh_from_db()
        self.assertEqual(interv.technicien_id, self.collegue.pk)

    # ── rôle système légacy « Responsable » (migration roles 0009) ──────
    def test_responsable_garde_exports_et_reaffectations(self):
        """Le palier Responsable exportait et réaffectait avant ASEC50 : le
        registre (et la migration 0009 pour les sociétés existantes) lui
        donne les codes — aucune régression pour ce rôle système."""
        from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
        from apps.sav.models import Ticket
        role = Role.objects.create(
            company=self.company, nom='Responsable', est_systeme=True,
            permissions=list(RESPONSABLE_PERMISSIONS))
        user = User.objects.create_user(
            username='asec50-responsable', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.force_authenticate(user)
        lead = self._lead()
        self.assertEqual(api.post(
            '/api/django/crm/leads/export-xlsx/', {'ids': [lead.pk]},
            format='json').status_code, 200)
        resp = api.get(
            f'/api/django/crm/clients/{self.client_obj.pk}/data-export/')
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = api.post('/api/django/crm/leads/bulk/', {
            'action': 'reassign', 'ids': [lead.pk],
            'owner': self.collegue.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.collegue.pk)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ASEC50-RESP',
            client=self.client_obj, equipe=self.equipe_a)
        resp = api.post(
            f'/api/django/sav/tickets/{ticket.pk}/reaffecter-equipe/',
            {'equipe': self.equipe_b.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
