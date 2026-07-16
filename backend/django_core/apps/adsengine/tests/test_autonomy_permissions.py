"""ADSENG47 — Tests des permissions fines du moteur autonome.

Deux permissions APPEND-ONLY (exception contractuelle n°3) : gérer les plans de
vol (``adsengine_flightplan_manage``, palier responsable+) et ACTIVER le mode
autonome (``adsengine_autonomy_toggle``, admin-SEUL). Prouve le gating rôle par
rôle — au niveau des listes de permissions ET des rôles réellement seedés par
``init_roles``.
"""
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company
from apps.roles import models as roles

FLIGHTPLAN = 'adsengine_flightplan_manage'
AUTONOMY = 'adsengine_autonomy_toggle'


class PermissionCatalogTests(TestCase):
    def test_both_permissions_registered(self):
        self.assertIn(FLIGHTPLAN, roles.ALL_PERMISSIONS)
        self.assertIn(AUTONOMY, roles.ALL_PERMISSIONS)

    def test_direction_tier_has_both(self):
        for perms in (roles.DIRECTEUR_PERMISSIONS, roles.ADMIN_PERMISSIONS):
            self.assertIn(FLIGHTPLAN, perms)
            self.assertIn(AUTONOMY, perms)

    def test_responsable_tier_manages_flightplans_not_autonomy(self):
        for perms in (roles.COMMERCIAL_RESP_PERMISSIONS,
                      roles.TECHNICIEN_RESP_PERMISSIONS):
            self.assertIn(FLIGHTPLAN, perms)
            self.assertNotIn(AUTONOMY, perms)

    def test_non_responsable_tier_has_neither(self):
        for perms in (roles.COMMERCIAL_PERMISSIONS,
                      roles.TECHNICIEN_PERMISSIONS,
                      roles.VIEWER_PERMISSIONS,
                      roles.UTILISATEUR_PERMISSIONS):
            self.assertNotIn(FLIGHTPLAN, perms)
            self.assertNotIn(AUTONOMY, perms)

    def test_autonomy_toggle_is_admin_only(self):
        # Aucun rôle canonique HORS Directeur/Administrateur ne porte l'activation
        # de l'autonomie.
        for nom, perms in roles.CANONICAL_SYSTEM_ROLES:
            if nom in ('Directeur', 'Administrateur'):
                self.assertIn(AUTONOMY, perms, nom)
            else:
                self.assertNotIn(AUTONOMY, perms, nom)


class InitRolesSeedingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RBAC Co', slug='rbac-co')

    def _perms(self, nom):
        call_command('init_roles')
        role = roles.Role.objects.get(company=self.company, nom=nom)
        return role.permissions

    def test_seeded_directeur_has_both(self):
        perms = self._perms('Directeur')
        self.assertIn(FLIGHTPLAN, perms)
        self.assertIn(AUTONOMY, perms)

    def test_seeded_commercial_responsable_flightplan_only(self):
        perms = self._perms('Commercial responsable')
        self.assertIn(FLIGHTPLAN, perms)
        self.assertNotIn(AUTONOMY, perms)

    def test_seeded_commercial_has_neither(self):
        perms = self._perms('Commercial')
        self.assertNotIn(FLIGHTPLAN, perms)
        self.assertNotIn(AUTONOMY, perms)
