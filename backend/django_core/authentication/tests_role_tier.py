"""Régression de contrôle d'accès : le palier de menu et l'accès aux écrans
d'administration doivent dériver du NOUVEAU rôle, jamais du champ legacy.

Bug constaté : un compte portant le rôle « Administrateur » ou « Responsable »
recevait le menu limité, parce que ``role_legacy`` restait figé à 'normal' à la
création de l'utilisateur, et que le frontend choisit le menu d'après ce champ
legacy. Le palier faisant autorité (``menu_tier``) doit venir du Role assigné.

Comportement attendu :
  - Administrateur ET Responsable → palier complet ('admin' / 'responsable').
  - Utilisateur et tout rôle personnalisé (ex. « Commercial ») → palier limité
    ('normal'), et toujours bloqué sur Paramètres / Utilisateurs / Rôles.
  - Le Responsable est promu : il atteint Paramètres / Utilisateurs / Rôles.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import (
    Role,
    ALL_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
    UTILISATEUR_PERMISSIONS,
)

User = get_user_model()


class RoleTierBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Tier Co', slug='tier-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.user_role = Role.objects.create(
            company=self.company, nom='Utilisateur',
            permissions=UTILISATEUR_PERMISSIONS, est_systeme=True)
        # Rôle personnalisé : relève du palier limité quelles que soient ses
        # permissions.
        self.commercial_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'ventes_voir', 'ventes_creer'],
            est_systeme=False)
        # Un propriétaire admin pour piloter les endpoints d'administration.
        self.owner = User.objects.create_user(
            username='owner', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)

    def _client_for(self, user):
        api = APIClient()
        token = str(AccessToken.for_user(user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api


class TestMenuTierResolution(RoleTierBase):
    """(a)(b)(c) Le palier de menu dérive du Role, pas du legacy figé."""

    def test_administrateur_role_resolves_to_full_tier(self):
        # Reproduit le bug : rôle Administrateur mais role_legacy au défaut.
        u = User.objects.create_user(
            username='a1', password='x', role=self.admin_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'admin')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['menu_tier'], 'admin')

    def test_responsable_role_resolves_to_full_tier(self):
        u = User.objects.create_user(
            username='r1', password='x', role=self.resp_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'responsable')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['menu_tier'], 'responsable')

    def test_utilisateur_role_resolves_to_limited_tier(self):
        u = User.objects.create_user(
            username='u1', password='x', role=self.user_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'normal')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.data['menu_tier'], 'normal')

    def test_custom_commercial_role_resolves_to_limited_tier(self):
        u = User.objects.create_user(
            username='c1', password='x', role=self.commercial_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'normal')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.data['menu_tier'], 'normal')


class TestAdminScreenAccess(RoleTierBase):
    """(b)(c) Paramètres / Utilisateurs / Rôles : ouverts à Admin + Responsable,
    toujours fermés au palier limité (Utilisateur / Commercial)."""

    def test_responsable_reaches_parametres_users_roles(self):
        u = User.objects.create_user(
            username='r2', password='x', role=self.resp_role,
            company=self.company)
        api = self._client_for(u)
        # Paramètres : lecture + écriture.
        self.assertEqual(api.get('/api/django/parametres/').status_code, 200)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'X'},
                      format='json').status_code, 200)
        # Utilisateurs.
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        # Rôles : lecture + écriture.
        self.assertEqual(api.get('/api/django/roles/').status_code, 200)
        created = api.post('/api/django/roles/',
                           {'nom': 'Rôle Resp', 'permissions': ['crm_voir']},
                           format='json')
        self.assertEqual(created.status_code, 201, created.data)

    def test_admin_reaches_parametres_users_roles(self):
        api = self._client_for(self.owner)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'Y'},
                      format='json').status_code, 200)
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        self.assertEqual(api.get('/api/django/roles/').status_code, 200)

    def test_utilisateur_is_blocked_from_admin_screens(self):
        u = User.objects.create_user(
            username='u2', password='x', role=self.user_role,
            company=self.company)
        api = self._client_for(u)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'Z'},
                      format='json').status_code, 403)
        self.assertEqual(api.get('/api/django/users/').status_code, 403)
        self.assertEqual(api.get('/api/django/roles/').status_code, 403)

    def test_commercial_custom_role_is_blocked_from_admin_screens(self):
        u = User.objects.create_user(
            username='c2', password='x', role=self.commercial_role,
            company=self.company)
        api = self._client_for(u)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'W'},
                      format='json').status_code, 403)
        self.assertEqual(api.get('/api/django/users/').status_code, 403)
        self.assertEqual(api.get('/api/django/roles/').status_code, 403)


class TestRoleLegacyStaysConsistent(RoleTierBase):
    """(d) La création/modification d'un utilisateur ne fige plus role_legacy
    à 'normal' : il suit le palier du Role assigné."""

    def test_create_user_via_api_with_admin_role_sets_admin_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/users/', {
            'username': 'newadmin', 'password': 'secretpass1',
            'email': 'n@n.com', 'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='newadmin')
        self.assertEqual(created.role_legacy, 'admin')
        self.assertEqual(created.menu_tier, 'admin')

    def test_register_view_with_admin_role_sets_admin_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/register/', {
            'username': 'regadmin', 'password': 'secretpass1',
            'email': 'r@r.com', 'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='regadmin')
        self.assertEqual(created.role_legacy, 'admin')

    def test_create_user_with_responsable_role_sets_responsable_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/users/', {
            'username': 'newresp', 'password': 'secretpass1',
            'email': 'rr@n.com', 'role': self.resp_role.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='newresp')
        self.assertEqual(created.role_legacy, 'responsable')

    def test_create_user_with_commercial_role_stays_normal_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/users/', {
            'username': 'newcom', 'password': 'secretpass1',
            'email': 'co@n.com', 'role': self.commercial_role.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='newcom')
        self.assertEqual(created.role_legacy, 'normal')

    def test_changing_role_via_patch_updates_legacy_tier(self):
        promoted = User.objects.create_user(
            username='promote', password='x', role=self.user_role,
            role_legacy='normal', company=self.company)
        api = self._client_for(self.owner)
        resp = api.patch(f'/api/django/users/{promoted.id}/',
                         {'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        promoted.refresh_from_db()
        self.assertEqual(promoted.role_legacy, 'admin')
        self.assertEqual(promoted.menu_tier, 'admin')


class TestBackfillExistingAccounts(RoleTierBase):
    """Les comptes existants déjà dérivés (role_legacy figé) sont réalignés sans
    re-création, par une fonction idempotente et non destructive."""

    def test_backfill_aligns_drifted_admin_account(self):
        from authentication.role_tiers import sync_role_legacy
        u = User.objects.create_user(
            username='drift', password='x', role=self.admin_role,
            company=self.company)
        # Force l'état AVANT correctif : legacy figé à 'normal'.
        User.objects.filter(pk=u.pk).update(role_legacy='normal')
        u.refresh_from_db()
        self.assertEqual(u.role_legacy, 'normal')

        changed = sync_role_legacy(User)

        u.refresh_from_db()
        self.assertEqual(u.role_legacy, 'admin')
        self.assertEqual(u.menu_tier, 'admin')
        self.assertGreaterEqual(changed, 1)

    def test_backfill_is_idempotent(self):
        from authentication.role_tiers import sync_role_legacy
        sync_role_legacy(User)
        # Deuxième passage : plus aucun changement.
        self.assertEqual(sync_role_legacy(User), 0)


class TestIsResponsableTightening(RoleTierBase):
    """ERR4 : ``is_responsable`` (et donc ``IsResponsableOrAdmin``) ne doit plus
    être vrai pour un rôle STRICTEMENT lecture seule. Les rôles métier qui
    détiennent une permission d'écriture/gestion le restent, ainsi que les
    comptes hérités sans rôle fin."""

    def _role(self, nom, perms):
        return Role.objects.create(
            company=self.company, nom=nom, permissions=perms,
            est_systeme=False)

    def test_readonly_viewer_role_is_not_responsable(self):
        viewer = User.objects.create_user(
            username='viewer_ro', password='x', company=self.company,
            role=self._role('Lecture seule', [
                'stock_voir', 'crm_voir', 'ventes_voir',
                'records_scope_equipe']))
        self.assertFalse(viewer.is_responsable)

    def test_utilisateur_role_is_not_responsable(self):
        u = User.objects.create_user(
            username='util_ro', password='x', company=self.company,
            role=self.user_role)
        self.assertFalse(u.is_responsable)

    def test_role_with_any_write_permission_is_responsable(self):
        com = User.objects.create_user(
            username='com_w', password='x', company=self.company,
            role=self._role('Commercial w', [
                'crm_voir', 'crm_creer', 'ventes_voir']))
        self.assertTrue(com.is_responsable)

    def test_admin_role_is_responsable(self):
        a = User.objects.create_user(
            username='adm_r', password='x', company=self.company,
            role=self.admin_role)
        self.assertTrue(a.is_responsable)

    def test_legacy_responsable_account_stays_responsable(self):
        legacy = User.objects.create_user(
            username='legacy_r', password='x', company=self.company,
            role_legacy='responsable')
        self.assertTrue(legacy.is_responsable)

    def test_legacy_normal_account_is_not_responsable(self):
        legacy = User.objects.create_user(
            username='legacy_n', password='x', company=self.company,
            role_legacy='normal')
        self.assertFalse(legacy.is_responsable)

    def test_readonly_role_blocked_from_responsable_endpoint(self):
        """Bout-en-bout : un rôle lecture seule est refusé sur un endpoint
        d'écriture gardé par ``IsResponsableOrAdmin`` (création de rôle via
        l'API roles, qui passe par le palier ; ici on vérifie l'effet
        ``is_responsable`` sur un endpoint ventes générique)."""
        viewer = User.objects.create_user(
            username='viewer_block', password='x', company=self.company,
            role=self._role('RO2', ['ventes_voir', 'crm_voir']))
        self.assertFalse(viewer.is_responsable)


class TestVX199SensitiveActionsFineGate(RoleTierBase):
    """VX199 — les ACTIONS SENSIBLES ventes (accepter un devis / émettre une
    facture) exigent la permission ERP FINE ``ventes_valider``, pas la garde
    grossière ``IsResponsableOrAdmin``.

    Le piège ERR4 : un rôle « lecture + UNE écriture » (ex. Commercial qui
    ne peut que créer des leads) rend ``is_responsable`` vrai — il FRANCHIT donc
    ``IsResponsableOrAdmin`` — alors qu'il n'a AUCUN droit de valider un devis
    ou d'émettre une facture. Ces deux endpoints doivent lui répondre 403.
    Les rôles qui portent réellement ``ventes_valider``, et les comptes hérités
    admin/directeur sans rôle fin, gardent l'accès.

    Test d'ALIGNEMENT front↔back : la surface exposée par ``/auth/me`` (les
    ``permissions`` que le frontend consomme pour cacher/afficher le bouton via
    ``useCanValiderDevis``/``useCanEmettreFacture``) contient ``ventes_valider``
    SI ET SEULEMENT SI le backend n'oppose pas 403 — donc l'écran et l'API ne
    peuvent pas diverger."""

    import django.utils.timezone as _tz
    _MONTH = _tz.now().strftime('%Y%m')

    def setUp(self):
        super().setUp()
        from decimal import Decimal
        from apps.crm.models import Client
        from apps.ventes.models import Devis, Facture

        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='VX199',
            email='vx199@example.com', telephone='+212600000199')
        self.devis = Devis.objects.create(
            company=self.company,
            reference=f'DEV-{self._MONTH}-9001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.facture = Facture.objects.create(
            company=self.company,
            reference=f'FAC-{self._MONTH}-9001',
            devis=self.devis, client=self.client_obj,
            statut=Facture.Statut.BROUILLON, type_facture='acompte',
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), created_by=self.owner)

        # Rôle « lecture + UNE écriture » — franchit le contrôle grossier
        # ``is_responsable`` (ERR4) mais NE porte PAS ``ventes_valider``.
        self.read_plus_one_write = User.objects.create_user(
            username='vx199_rw', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Commercial VX199',
                permissions=['ventes_voir', 'crm_voir', 'crm_creer'],
                est_systeme=False))
        # Rôle qui porte réellement la validation ventes.
        self.valideur = User.objects.create_user(
            username='vx199_valideur', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Valideur VX199',
                permissions=['ventes_voir', 'ventes_valider'],
                est_systeme=False))
        # Compte hérité admin (sans rôle fin) : repli historique.
        self.legacy_admin = User.objects.create_user(
            username='vx199_legacy_admin', password='x', company=self.company,
            role_legacy='admin')

    def _accepter(self, user):
        return self._client_for(user).post(
            f'/api/django/ventes/devis/{self.devis.id}/accepter/',
            {}, format='json')

    def _emettre(self, user):
        return self._client_for(user).post(
            f'/api/django/ventes/factures/{self.facture.id}/emettre/',
            {}, format='json')

    # ── Le read+one-write franchit bien la garde grossière (preuve du piège) ──
    def test_read_plus_one_write_role_is_responsable(self):
        self.assertTrue(self.read_plus_one_write.is_responsable)
        self.assertFalse(
            self.read_plus_one_write.has_erp_permission('ventes_valider'))

    # ── DoD : 403 sur les deux actions sensibles ──────────────────────────────
    def test_read_plus_one_write_role_forbidden_to_accepter_devis(self):
        self.assertEqual(self._accepter(self.read_plus_one_write).status_code,
                         403)

    def test_read_plus_one_write_role_forbidden_to_emettre_facture(self):
        self.assertEqual(self._emettre(self.read_plus_one_write).status_code,
                         403)

    # ── Les porteurs légitimes de ``ventes_valider`` ne sont PAS bloqués ──────
    def test_role_with_ventes_valider_not_forbidden_to_accepter(self):
        self.assertNotEqual(self._accepter(self.valideur).status_code, 403)

    def test_role_with_ventes_valider_not_forbidden_to_emettre(self):
        self.assertNotEqual(self._emettre(self.valideur).status_code, 403)

    # ── Repli historique : admin/directeur legacy sans rôle fin passent ───────
    def test_legacy_admin_not_forbidden_to_accepter(self):
        self.assertNotEqual(self._accepter(self.legacy_admin).status_code, 403)

    def test_legacy_admin_not_forbidden_to_emettre(self):
        self.assertNotEqual(self._emettre(self.legacy_admin).status_code, 403)

    # ── Alignement front↔back dérivé de /auth/me (pas d'une constante figée) ──
    def test_front_back_alignment_via_auth_me(self):
        for user, must_be_403 in (
            (self.read_plus_one_write, True),
            (self.valideur, False),
        ):
            api = self._client_for(user)
            me = api.get('/api/django/auth/me/')
            self.assertEqual(me.status_code, 200, me.data)
            front_can = 'ventes_valider' in (me.data.get('permissions') or [])
            back_403 = self._accepter(user).status_code == 403
            # Le bouton front (front_can) est visible ⇔ l'API n'oppose pas 403.
            self.assertEqual(front_can, not back_403)
            self.assertEqual(back_403, must_be_403)
