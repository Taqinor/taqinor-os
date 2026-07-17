"""NTPRT1 — rôle portail scopé sur ``CustomUser`` (fondation DONNÉE).

Couvre :
- ``CustomUser.portee`` par défaut = ``interne`` (comportement inchangé : tout
  compte existant reste interne) ;
- un compte portail se crée avec ``portee=portail_client`` + son
  ``portail_client_id`` (string-ref entier, jamais un FK cross-app) ;
- ``init_roles`` sème EXACTEMENT les 3 rôles système portail avec
  ``est_systeme=True`` et des permissions PORTAIL-SEULES (aucun code interne du
  catalogue ``ALL_PERMISSIONS``), de façon IDEMPOTENTE (2 exécutions ⇒ aucun
  doublon) ;
- garde de sécurité : un compte portail n'est JAMAIS « responsable » ni
  « admin » interne (il ne peut franchir aucune garde interne d'écriture).

La classe de permission d'enforcement (accès borné aux endpoints
``/api/django/portail/*`` de SON id) n'est PAS construite ici — c'est NTPRT5.
"""
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company, CustomUser
from apps.roles.models import (
    ALL_PERMISSIONS,
    CANONICAL_PORTAIL_ROLES,
    Role,
)


PORTAIL_ROLE_NAMES = {nom for nom, _ in CANONICAL_PORTAIL_ROLES}
PORTAIL_PERMS = {nom: list(perms) for nom, perms in CANONICAL_PORTAIL_ROLES}


class CustomUserPorteeFieldTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Portée Co', slug='portee-co')

    def test_defaut_interne(self):
        """Un compte fraîchement créé est INTERNE par défaut."""
        user = CustomUser.objects.create_user(
            username='interne1', password='x', company=self.company)
        self.assertEqual(user.portee, CustomUser.PORTEE_INTERNE)
        self.assertEqual(user.portee, 'interne')
        # Les ids de rattachement portail restent NULL pour un compte interne.
        self.assertIsNone(user.portail_client_id)
        self.assertIsNone(user.portail_fournisseur_id)
        self.assertIsNone(user.portail_partenaire_id)

    def test_creation_compte_portail_client(self):
        """Un compte portail client se crée avec portee + portail_client_id."""
        user = CustomUser.objects.create_user(
            username='client_portail', password='x', company=self.company,
            portee=CustomUser.PORTEE_PORTAIL_CLIENT,
            portail_client_id=4242,
        )
        user.refresh_from_db()
        self.assertEqual(user.portee, 'portail_client')
        self.assertEqual(user.portail_client_id, 4242)
        # string-ref : c'est un entier simple, pas un objet/relation.
        self.assertIsInstance(user.portail_client_id, int)
        # Les autres ids restent NULL (rattachement à UNE seule entité).
        self.assertIsNone(user.portail_fournisseur_id)
        self.assertIsNone(user.portail_partenaire_id)


class InitRolesPortailSeedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Seed Co', slug='seed-co')

    def _portail_roles(self):
        return Role.objects.filter(
            company=self.company, nom__in=PORTAIL_ROLE_NAMES)

    def test_init_roles_seme_les_3_roles_portail(self):
        call_command('init_roles')
        roles = self._portail_roles()
        self.assertEqual(roles.count(), 3)
        noms = set(roles.values_list('nom', flat=True))
        self.assertEqual(noms, PORTAIL_ROLE_NAMES)

        interne_codes = set(ALL_PERMISSIONS)
        for role in roles:
            # Rôle SYSTÈME.
            self.assertTrue(
                role.est_systeme,
                f'Le rôle portail « {role.nom} » doit être système.')
            # Permissions attendues (portail-seules).
            self.assertEqual(role.permissions, PORTAIL_PERMS[role.nom])
            # AUCUN code interne du catalogue ALL_PERMISSIONS.
            self.assertEqual(
                set(role.permissions) & interne_codes, set(),
                f'Le rôle portail « {role.nom} » ne doit porter AUCUNE '
                f'permission interne.')
            # Tous les codes sont bien des marqueurs portail.
            for code in role.permissions:
                self.assertTrue(code.startswith('portail_'))

    def test_init_roles_idempotent(self):
        """Deux exécutions ⇒ toujours exactement 3 rôles portail, sans doublon."""
        call_command('init_roles')
        first_ids = set(self._portail_roles().values_list('id', flat=True))
        call_command('init_roles')
        second = self._portail_roles()
        self.assertEqual(second.count(), 3)
        # Mêmes lignes (get_or_create réutilise, ne recrée pas).
        self.assertEqual(
            set(second.values_list('id', flat=True)), first_ids)


class PortailUserNeverInternalTests(TestCase):
    """Un compte portail ne doit JAMAIS être « responsable »/« admin » interne."""

    def setUp(self):
        self.company = Company.objects.create(nom='Guard Co', slug='guard-co')
        call_command('init_roles')

    def test_compte_portail_pas_responsable_ni_admin(self):
        role = Role.objects.get(company=self.company, nom='Portail client')
        user = CustomUser.objects.create_user(
            username='cli', password='x', company=self.company, role=role,
            portee=CustomUser.PORTEE_PORTAIL_CLIENT, portail_client_id=1)
        # Le marqueur portail n'accorde AUCUN droit d'écriture interne.
        self.assertFalse(user.is_responsable)
        self.assertFalse(user.is_admin_role)
        # Ni aucune permission interne fine.
        self.assertFalse(user.has_erp_permission('crm_voir'))
        self.assertFalse(user.has_erp_permission('ventes_creer'))
        self.assertFalse(user.has_erp_permission('roles_gerer'))
