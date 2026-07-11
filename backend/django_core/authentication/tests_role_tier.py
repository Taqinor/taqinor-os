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
    """VX199 — les actions SENSIBLES (validation de devis, émission de facture)
    ne doivent plus passer via la garde grossière ``IsResponsableOrAdmin`` : un
    compte « lecture + UNE écriture » (donc ``is_responsable`` == True, ex. un
    rôle qui n'a que ``crm_creer``) est désormais refusé (403) faute de la
    permission fine ``ventes_valider``.  Les comptes hérités responsable/admin
    et les rôles qui DÉTIENNENT ``ventes_valider`` continuent de passer la
    garde (HasPermissionOrLegacy).
    """

    def _role(self, nom, perms):
        return Role.objects.create(
            company=self.company, nom=nom, permissions=perms,
            est_systeme=False)

    def _client_obj(self):
        from apps.crm.models import Client
        return Client.objects.create(
            company=self.company, nom='Cli', prenom='VX199',
            email='vx199@example.com', telephone='+212600009199')

    def _devis(self):
        from decimal import Decimal
        from django.utils import timezone
        from apps.ventes.models import Devis
        month = timezone.now().strftime('%Y%m')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{month}-9199',
            client=self._client_obj(), statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))

    def _facture(self):
        from decimal import Decimal
        from apps.ventes.models import Facture, LigneFacture
        from apps.stock.models import Produit
        cli = self._client_obj()
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-VX199',
            prix_vente=Decimal('5000'), quantite_stock=10,
            tva=Decimal('20.00'))
        facture = Facture.objects.create(
            company=self.company, reference='FAC-VX199-0001',
            client=cli, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        return facture

    # ── Validation de devis (accepter) ───────────────────────────────────
    def test_read_plus_one_write_role_forbidden_to_accepter_devis(self):
        """Un rôle « lecture + une écriture » SANS ventes_valider → 403."""
        user = User.objects.create_user(
            username='vx199_rw_devis', password='x', company=self.company,
            role=self._role('LeadWriter', ['crm_voir', 'crm_creer',
                                           'ventes_voir']))
        # Garde grossière historique : ce rôle passait (une écriture posée).
        self.assertTrue(user.is_responsable)
        devis = self._devis()
        resp = self._client_for(user).post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_role_with_ventes_valider_passes_accepter_gate(self):
        """Un rôle qui détient ventes_valider franchit la garde (pas 403)."""
        user = User.objects.create_user(
            username='vx199_valider_devis', password='x',
            company=self.company,
            role=self._role('Valideur', ['ventes_voir', 'ventes_creer',
                                         'ventes_valider']))
        devis = self._devis()
        resp = self._client_for(user).post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'X'}, format='json')
        self.assertNotEqual(resp.status_code, 403, resp.data)

    def test_legacy_responsable_passes_accepter_gate(self):
        """Compte hérité responsable (sans rôle fin) : comportement préservé."""
        user = User.objects.create_user(
            username='vx199_legacy_devis', password='x',
            company=self.company, role_legacy='responsable')
        devis = self._devis()
        resp = self._client_for(user).post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'X'}, format='json')
        self.assertNotEqual(resp.status_code, 403, resp.data)

    # ── Émission de facture (emettre) ────────────────────────────────────
    def test_read_plus_one_write_role_forbidden_to_emettre_facture(self):
        user = User.objects.create_user(
            username='vx199_rw_fac', password='x', company=self.company,
            role=self._role('LeadWriter2', ['crm_voir', 'crm_creer',
                                            'ventes_voir']))
        self.assertTrue(user.is_responsable)
        facture = self._facture()
        resp = self._client_for(user).post(
            f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_role_with_ventes_valider_passes_emettre_gate(self):
        user = User.objects.create_user(
            username='vx199_valider_fac', password='x', company=self.company,
            role=self._role('Valideur2', ['ventes_voir', 'ventes_creer',
                                          'ventes_valider']))
        facture = self._facture()
        resp = self._client_for(user).post(
            f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertNotEqual(resp.status_code, 403, resp.data)

    def test_legacy_responsable_passes_emettre_gate(self):
        user = User.objects.create_user(
            username='vx199_legacy_fac', password='x', company=self.company,
            role_legacy='responsable')
        facture = self._facture()
        resp = self._client_for(user).post(
            f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertNotEqual(resp.status_code, 403, resp.data)


class TestVX199FrontBackAlignment(TestCase):
    """VX199 — parité front↔back : le code de permission ERP sur lequel le
    frontend gate les actions sensibles de validation ventes doit être
    EXACTEMENT celui que le backend exige sur les endpoints (accepter /
    emettre). Le test échoue si la constante frontend
    (``VENTES_VALIDER_PERMISSION`` dans ``useHasPermission.js``) diverge du
    code réellement gardé côté backend, ou si ce code sort du catalogue
    ``ALL_PERMISSIONS``.
    """

    #: Code de permission fine gardant accepter (devis) + emettre (facture).
    BACKEND_SENSITIVE_CODE = 'ventes_valider'

    def test_backend_code_is_a_real_permission(self):
        self.assertIn(self.BACKEND_SENSITIVE_CODE, ALL_PERMISSIONS)

    def test_backend_endpoints_gate_on_the_sensitive_code(self):
        """Le décorateur des actions sensibles porte bien
        HasPermissionOrLegacy(<code>)."""
        from apps.ventes.views.devis import DevisViewSet
        from apps.ventes.views.facture import FactureViewSet
        for viewset, method in (
                (DevisViewSet, 'accepter'), (FactureViewSet, 'emettre')):
            perms = getattr(
                viewset, method).kwargs['permission_classes']
            names = [getattr(p, '__name__', '') for p in perms]
            self.assertIn(
                f'HasPermissionOrLegacy_{self.BACKEND_SENSITIVE_CODE}', names,
                f'{viewset.__name__}.{method} ne garde pas '
                f'{self.BACKEND_SENSITIVE_CODE}')

    def test_frontend_constant_matches_backend_code(self):
        """La constante frontend est la seule source de gating côté écran ;
        elle DOIT valoir le code backend. Lecture du fichier source (pas de
        build JS) pour garder le test hermétique."""
        import os
        import re
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # backend/django_core/authentication/ → remonter à la racine repo.
        repo_root = os.path.dirname(os.path.dirname(here))
        hook = os.path.join(
            repo_root, 'frontend', 'src', 'hooks', 'useHasPermission.js')
        self.assertTrue(os.path.exists(hook), hook)
        with open(hook, encoding='utf-8') as fh:
            src = fh.read()
        m = re.search(
            r"VENTES_VALIDER_PERMISSION\s*=\s*'([^']+)'", src)
        self.assertIsNotNone(
            m, 'VENTES_VALIDER_PERMISSION introuvable dans useHasPermission.js')
        self.assertEqual(m.group(1), self.BACKEND_SENSITIVE_CODE)
