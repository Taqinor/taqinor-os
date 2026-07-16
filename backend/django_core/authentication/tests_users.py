"""Tests gestion employés (admin) : poste, avatar, mot de passe.

L'upload réel de la photo passe par MinIO (boto3) — même chemin éprouvé que
le logo d'entreprise. On teste ici la surface API (édition du poste, garde
admin, validation d'upload, réinitialisation de mot de passe), sans dépendre
du conteneur objet pour rester hermétique.
"""
from io import BytesIO
from unittest import mock
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ALL_PERMISSIONS, RESPONSABLE_PERMISSIONS

User = get_user_model()

# En-tête PNG minimal valide (octets magiques reconnus par _detect_image_type).
_PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40


class _FakeMinio:
    """Client MinIO en mémoire : prouve le round-trip upload → fetch sans réseau.

    Stocke les octets par (bucket, key) ; ``get_object`` les rend via un flux
    ``Body`` au contrat boto3 (.read())."""

    def __init__(self, store):
        self._store = store

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        self._store[(bucket, key)] = fileobj.read()

    def get_object(self, Bucket, Key):
        data = self._store[(Bucket, Key)]
        return {'Body': BytesIO(data)}

    def delete_object(self, Bucket, Key):
        self._store.pop((Bucket, Key), None)

    def head_bucket(self, Bucket):
        return {}

    def create_bucket(self, Bucket):
        return {}


class TestEmployeeAdmin(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Emp Co', slug='emp-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True,
        )
        self.admin = User.objects.create_user(
            username='emp_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company,
        )
        self.employee = User.objects.create_user(
            username='emp_one', password='oldpass', role_legacy='normal',
            company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_admin_can_edit_poste(self):
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'poste': 'Commerciale'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.poste, 'Commerciale')
        self.assertEqual(resp.data['poste'], 'Commerciale')

    def test_admin_can_set_new_password(self):
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'password': 'brandnew123'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password('brandnew123'))
        # Le mot de passe n'est jamais renvoyé en clair.
        self.assertNotIn('password', resp.data)

    def test_avatar_key_not_writable_via_patch(self):
        resp = self.api.patch(
            f'/api/django/users/{self.employee.id}/',
            {'avatar_key': 'avatars/forged.png'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.avatar_key, '')

    def test_avatar_upload_requires_file(self):
        resp = self.api.post(
            f'/api/django/users/{self.employee.id}/avatar/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_avatar_endpoint_blocks_limited_tier_allows_responsable(self):
        # Gestion des utilisateurs (dont l'avatar) : ouverte à l'Administrateur
        # ET au Responsable (promu), fermée au palier limité.
        commerciale_role = Role.objects.create(
            company=self.company, nom='Commerciale',
            permissions=['crm_voir', 'ventes_voir'], est_systeme=False,
        )
        commerciale = User.objects.create_user(
            username='emp_comm', password='x', role=commerciale_role,
            company=self.company,
        )
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commerciale)}')
        resp = api.post(
            f'/api/django/users/{self.employee.id}/avatar/', {}, format='multipart')
        self.assertEqual(resp.status_code, 403)

        # Le Responsable est autorisé : 400 (aucun fichier) prouve que la garde
        # de permission est passée.
        resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True,
        )
        resp_user = User.objects.create_user(
            username='emp_resp', password='x', role=resp_role,
            company=self.company,
        )
        api2 = APIClient()
        api2.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(resp_user)}')
        resp2 = api2.post(
            f'/api/django/users/{self.employee.id}/avatar/', {}, format='multipart')
        self.assertEqual(resp2.status_code, 400)

    def test_user_serializer_exposes_avatar_url_field(self):
        resp = self.api.get(f'/api/django/users/{self.employee.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('avatar_url', resp.data)
        self.assertIn('poste', resp.data)

    # ── T-U13 : la photo de profil se téléverse ET se RÉAFFICHE ─────────────
    def _upload_png(self, store, *, name='photo.png'):
        """Téléverse un PNG via l'endpoint avatar avec un MinIO en mémoire."""
        fake = _FakeMinio(store)
        upload = SimpleUploadedFile(name, _PNG_BYTES, content_type='image/png')
        with mock.patch('authentication.avatars.get_minio_client',
                        return_value=fake), \
             mock.patch('authentication.avatars.ensure_uploads_bucket'):
            return self.api.post(
                f'/api/django/users/{self.employee.id}/avatar/',
                {'file': upload}, format='multipart')

    def test_avatar_url_is_reachable_same_origin_not_internal_minio(self):
        """RÉGRESSION T-U13 — bug racine : ``avatar_url`` pointait sur l'hôte
        INTERNE MinIO (``minio:9000``), injoignable depuis le navigateur. La
        photo ne s'affichait jamais (initiales seules). L'URL doit désormais
        être un chemin de MÊME ORIGINE vers le proxy Django."""
        store = {}
        resp = self._upload_png(store)
        self.assertEqual(resp.status_code, 200, resp.data)
        url = resp.data['avatar_url']
        self.assertIsNotNone(url)
        # Chemin relatif de même origine — jamais l'hôte interne MinIO.
        self.assertTrue(url.startswith('/api/django/users/avatar-image/'), url)
        self.assertNotIn('minio', url)
        self.assertNotIn('9000', url)
        self.assertNotIn('http://', url)
        # La clé stockée est bien transportée (encodée) dans l'URL.
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.avatar_key.startswith('avatars/'))
        self.assertIn(quote(self.employee.avatar_key, safe=''), url)

    def test_avatar_upload_then_fetch_renders_stored_bytes(self):
        """Chaîne complète : upload → clé stockée → URL atteignable → octets
        servis. Le proxy renvoie l'image avec un type MIME image."""
        store = {}
        resp = self._upload_png(store)
        self.assertEqual(resp.status_code, 200, resp.data)
        url = resp.data['avatar_url']

        fake = _FakeMinio(store)
        with mock.patch('authentication.avatars.get_minio_client',
                        return_value=fake):
            img = self.api.get(url)
        self.assertEqual(img.status_code, 200)
        self.assertTrue(img['Content-Type'].startswith('image/'), img)
        self.assertEqual(img.content, _PNG_BYTES)

    def test_sca42_new_avatar_key_is_company_prefixed(self):
        """SCA42 — la clé du NOUVEL upload est préfixée par la société
        (``avatars/{company_id}/{uuid}.ext``), pas plate. Isole le stockage
        objet par tenant (motif ERR75)."""
        store = {}
        resp = self._upload_png(store)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        key = self.employee.avatar_key
        self.assertTrue(
            key.startswith(f'avatars/{self.company.id}/'),
            f'clé non préfixée société : {key}')

    def test_sca42_old_flat_avatar_key_still_served(self):
        """SCA42 — un objet DÉJÀ stocké sous une clé PLATE (ancien format
        ``avatars/{uuid}.png``) reste servi : la lecture utilise la clé
        STOCKÉE, aucune migration de données n'est requise."""
        old_key = 'avatars/legacyflatkey.png'
        store = {('erp-uploads', old_key): _PNG_BYTES}
        self.employee.avatar_key = old_key
        self.employee.save(update_fields=['avatar_key'])
        url = f'/api/django/users/avatar-image/?key={quote(old_key, safe="")}'
        fake = _FakeMinio(store)
        with mock.patch('authentication.avatars.get_minio_client',
                        return_value=fake):
            img = self.api.get(url)
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img.content, _PNG_BYTES)

    def test_avatar_image_requires_authentication(self):
        store = {}
        self._upload_png(store)
        self.employee.refresh_from_db()
        key = self.employee.avatar_key
        anon = APIClient()
        resp = anon.get(
            f'/api/django/users/avatar-image/?key={quote(key, safe="")}')
        self.assertEqual(resp.status_code, 401)

    def test_avatar_image_rejects_non_avatar_key(self):
        """Le proxy ne relaie JAMAIS un objet hors du préfixe ``avatars/`` —
        pas de lecture arbitraire du bucket (logos, signatures, pièces jointes)."""
        for bad in ('logos/secret.png', 'avatars/../logos/x.png', '', 'x.png'):
            resp = self.api.get(
                '/api/django/users/avatar-image/?key=' + quote(bad, safe=''))
            self.assertEqual(resp.status_code, 404, bad)

    def test_avatar_image_open_to_limited_tier_authenticated_user(self):
        """La photo s'affiche partout (sélecteur de responsable côté
        Commerciale, kanban…), donc le PROXY de lecture est ouvert à tout
        utilisateur authentifié — même si l'écran Utilisateurs reste admin."""
        store = {}
        self._upload_png(store)
        self.employee.refresh_from_db()
        key = self.employee.avatar_key
        viewer_role = Role.objects.create(
            company=self.company, nom='Commerciale',
            permissions=['crm_voir'], est_systeme=False)
        viewer = User.objects.create_user(
            username='emp_view', password='x', role=viewer_role,
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(viewer)}')
        fake = _FakeMinio(store)
        with mock.patch('authentication.avatars.get_minio_client',
                        return_value=fake):
            resp = api.get(
                f'/api/django/users/avatar-image/?key={quote(key, safe="")}')
        self.assertEqual(resp.status_code, 200)


class TestRoleAssignmentN103(TestCase):
    """Régression N103 : un Directeur ET un Administrateur doivent pouvoir
    lister utilisateurs + rôles et changer FACILEMENT le rôle de n'importe quel
    utilisateur (persistant, effectif immédiatement), et assigner un superviseur.
    Le palier limité (Viewer/Commercial) reste bloqué (aucun affaiblissement).

    Cause racine : le palier de menu dérivait du nom + ``est_systeme`` du rôle.
    Un Directeur/Administrateur réel dont la ligne Role a dérivé (mapping
    rétroactif laissant ``est_systeme=False``) résolvait au palier limité → 403
    sur /users/ et /roles/ → l'écran ne chargeait plus → impossible de changer
    les rôles. Le palier dérive désormais d'abord du signal ``roles_gerer``."""

    def setUp(self):
        from apps.roles.models import (
            DIRECTEUR_PERMISSIONS, ADMIN_PERMISSIONS,
            COMMERCIAL_PERMISSIONS, VIEWER_PERMISSIONS,
        )
        self.company = Company.objects.create(nom='N103 Co', slug='n103-co')
        self.directeur_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.commercial_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        self.viewer_role = Role.objects.create(
            company=self.company, nom='Viewer',
            permissions=list(VIEWER_PERMISSIONS), est_systeme=True)

        # Propriétaire Directeur + un second admin (pour que rétrograder un admin
        # ne soit jamais bloqué par la garde « dernier propriétaire »).
        self.directeur = User.objects.create_user(
            username='dir', password='x', role=self.directeur_role,
            role_legacy='admin', company=self.company, is_protected=True)
        self.administrateur = User.objects.create_user(
            username='adm', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)
        # Cible ordinaire dont on change le rôle.
        self.employee = User.objects.create_user(
            username='emp', password='x', role=self.commercial_role,
            role_legacy='normal', company=self.company)

    def _client_for(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    # ── Endpoints atteignables par Directeur ET Administrateur ──────────────
    def test_directeur_reaches_users_and_roles(self):
        api = self._client_for(self.directeur)
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        self.assertEqual(api.get('/api/django/roles/').status_code, 200)

    def test_administrateur_reaches_users_and_roles(self):
        api = self._client_for(self.administrateur)
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        self.assertEqual(api.get('/api/django/roles/').status_code, 200)

    # ── Changement de rôle par Directeur ET Administrateur ──────────────────
    def test_directeur_can_change_user_role(self):
        api = self._client_for(self.directeur)
        resp = api.patch(f'/api/django/users/{self.employee.id}/',
                         {'role': self.viewer_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role_id, self.viewer_role.id)

    def test_administrateur_can_change_user_role(self):
        api = self._client_for(self.administrateur)
        resp = api.patch(f'/api/django/users/{self.employee.id}/',
                         {'role': self.viewer_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role_id, self.viewer_role.id)

    def test_admin_can_promote_user_to_admin_role(self):
        # Promotion vers un rôle admin : doit passer et réaligner le palier.
        api = self._client_for(self.directeur)
        resp = api.patch(f'/api/django/users/{self.employee.id}/',
                         {'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role_id, self.admin_role.id)
        self.assertEqual(self.employee.role_legacy, 'admin')
        self.assertEqual(self.employee.menu_tier, 'admin')

    def test_admin_can_demote_other_admin_role(self):
        # Rétrograder un admin qui n'est PAS le dernier propriétaire : autorisé.
        api = self._client_for(self.directeur)
        resp = api.patch(f'/api/django/users/{self.administrateur.id}/',
                         {'role': self.commercial_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.administrateur.refresh_from_db()
        self.assertEqual(self.administrateur.role_id, self.commercial_role.id)

    # ── Cause racine : Directeur dérivé (est_systeme=False) garde l'accès ────
    def test_drifted_directeur_still_admin_tier_and_reaches_endpoints(self):
        # Reproduit l'état laissé par le mapping rétroactif : la ligne Role
        # « Directeur » est restée est_systeme=False.
        self.directeur_role.est_systeme = False
        self.directeur_role.save(update_fields=['est_systeme'])
        self.directeur.refresh_from_db()
        self.assertEqual(self.directeur.menu_tier, 'admin')
        api = self._client_for(self.directeur)
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        self.assertEqual(api.get('/api/django/roles/').status_code, 200)
        # Et il peut toujours changer un rôle.
        resp = api.patch(f'/api/django/users/{self.employee.id}/',
                         {'role': self.viewer_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    # ── Assignation du superviseur (Paramètres → Équipe) ────────────────────
    def test_admin_can_assign_supervisor(self):
        api = self._client_for(self.directeur)
        resp = api.patch(f'/api/django/users/{self.employee.id}/',
                         {'supervisor': self.administrateur.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.supervisor_id, self.administrateur.id)
        self.assertEqual(resp.data['supervisor'], self.administrateur.id)

    def test_admin_can_clear_supervisor(self):
        self.employee.supervisor = self.administrateur
        self.employee.save(update_fields=['supervisor'])
        api = self._client_for(self.directeur)
        resp = api.patch(f'/api/django/users/{self.employee.id}/',
                         {'supervisor': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.supervisor_id)

    # ── Négatif : le palier limité reste bloqué (aucun affaiblissement) ─────
    def test_viewer_blocked_from_users_and_roles(self):
        viewer = User.objects.create_user(
            username='vw', password='x', role=self.viewer_role,
            company=self.company)
        api = self._client_for(viewer)
        self.assertEqual(api.get('/api/django/users/').status_code, 403)
        self.assertEqual(api.get('/api/django/roles/').status_code, 403)
        resp = api.patch(f'/api/django/users/{self.employee.id}/',
                         {'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_commercial_blocked_from_users_and_roles(self):
        commercial = User.objects.create_user(
            username='cm', password='x', role=self.commercial_role,
            company=self.company)
        api = self._client_for(commercial)
        self.assertEqual(api.get('/api/django/users/').status_code, 403)
        self.assertEqual(api.get('/api/django/roles/').status_code, 403)


class TestSystemRoleSeedingSelfHealsN103(TestCase):
    """N103 : le seeding des rôles système est auto-réparateur — une ligne du
    même nom laissée ``est_systeme=False`` est promue, pour qu'un Directeur/
    Administrateur ne reste jamais coincé au palier limité."""

    def test_init_roles_promotes_drifted_system_role(self):
        from django.core.management import call_command
        company = Company.objects.create(nom='Heal Co', slug='heal-co')
        # Ligne « Directeur » préexistante, mais est_systeme=False (dérive).
        drifted = Role.objects.create(
            company=company, nom='Directeur',
            permissions=['crm_voir'], est_systeme=False)
        owner = User.objects.create_user(
            username='healowner', password='x', role=drifted,
            role_legacy='admin', company=company, is_protected=True)

        call_command('init_roles')

        drifted.refresh_from_db()
        self.assertTrue(drifted.est_systeme)
        self.assertIn('roles_gerer', drifted.permissions)
        owner.refresh_from_db()
        self.assertEqual(owner.menu_tier, 'admin')


class TestRoleAssignmentGuards(TestCase):
    """ERR21 : l'assignation d'un ``role`` à un utilisateur est validée — le
    rôle doit appartenir à l'entreprise de l'assignateur, et seul un
    administrateur peut octroyer un rôle de palier admin (anti-escalade)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Assign Co', slug='assign-co')
        self.other = Company.objects.create(nom='Autre Co', slug='autre-assign')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.foreign_admin_role = Role.objects.create(
            company=self.other, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='ra_admin', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)
        # Responsable (palier promu, non-admin) : porte ``users_voir`` donc passe
        # IsAdminOrResponsableTier, mais n'est PAS admin (pas de roles_gerer).
        self.resp = User.objects.create_user(
            username='ra_resp', password='x', role=self.resp_role,
            role_legacy='responsable', company=self.company)
        self.target = User.objects.create_user(
            username='ra_target', password='x', role_legacy='normal',
            company=self.company)

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_responsable_cannot_grant_admin_role(self):
        resp = self._api(self.resp).patch(
            f'/api/django/users/{self.target.id}/',
            {'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.target.refresh_from_db()
        self.assertNotEqual(self.target.role_id, self.admin_role.id)

    def test_admin_can_grant_admin_role(self):
        resp = self._api(self.admin).patch(
            f'/api/django/users/{self.target.id}/',
            {'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role_id, self.admin_role.id)

    def test_cannot_assign_foreign_company_role(self):
        resp = self._api(self.admin).patch(
            f'/api/django/users/{self.target.id}/',
            {'role': self.foreign_admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.target.refresh_from_db()
        self.assertNotEqual(self.target.role_id, self.foreign_admin_role.id)

    def test_responsable_can_grant_non_admin_role(self):
        resp = self._api(self.resp).patch(
            f'/api/django/users/{self.target.id}/',
            {'role': self.resp_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role_id, self.resp_role.id)
