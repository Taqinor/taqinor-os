"""ASEC9 / D-ASEC-1 — code de droit ``encaisser`` (gestes d'argent).

* au catalogue, module affiché ``ventes`` (les factures n'ont pas de manifeste
  propre), NON élevé ;
* après ``init_roles`` : Directeur, Administrateur, Commercial, Commercial
  responsable le portent ; Commercial terrain, Technicien, Technicien
  responsable, Admin RH non ;
* la grille refuse son octroi à ces quatre rôles système (400), même pour un
  administrateur ;
* migration ``0007_asec9_code_encaisser`` : aller = ajout aux seuls rôles
  système autorisés, retour = retrait de tout rôle.
"""
import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ALL_PERMISSIONS,
    ELEVATED_PERMISSIONS,
    PERMISSION_MODULE,
)
from authentication.models import Company

User = get_user_model()

CODE = 'encaisser'
TITULAIRES = ('Directeur', 'Administrateur', 'Commercial',
              'Commercial responsable')
INTERDITS = ('Commercial terrain', 'Technicien', 'Technicien responsable',
             'Admin RH')


class CodeEncaisserTests(TestCase):
    def test_code_au_catalogue(self):
        self.assertEqual(ALL_PERMISSIONS.count(CODE), 1)
        self.assertNotIn(CODE, ELEVATED_PERMISSIONS)
        self.assertEqual(PERMISSION_MODULE.get(CODE), 'ventes')

    def test_titulaires_par_role_systeme(self):
        company = Company.objects.create(nom='ASEC9', slug='asec9-roles')
        call_command('init_roles', verbosity=0)
        roles = {r.nom: list(r.permissions)
                 for r in Role.objects.filter(company=company)}
        for nom in TITULAIRES:
            with self.subTest(role=nom):
                self.assertIn(CODE, roles[nom])
        for nom in INTERDITS:
            with self.subTest(role=nom):
                self.assertIn(nom, roles)
                self.assertNotIn(CODE, roles[nom])

    def test_octroi_interdit_refuse(self):
        company = Company.objects.create(nom='ASEC9 b', slug='asec9-grille')
        call_command('init_roles', verbosity=0)
        admin = User.objects.create_user(
            username='asec9_admin', password='x', company=company,
            role=Role.objects.get(company=company, nom='Administrateur'))
        api = APIClient()
        api.force_authenticate(admin)
        for nom in INTERDITS:
            role = Role.objects.get(company=company, nom=nom)
            avant = list(role.permissions)
            with self.subTest(role=nom):
                resp = api.patch(
                    f'/api/django/roles/{role.id}/',
                    {'permissions': avant + [CODE]}, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn('non octroyable', str(resp.data))
                role.refresh_from_db()
                self.assertEqual(role.permissions, avant)
        # Décocher reste possible sur un titulaire par défaut.
        com = Role.objects.get(company=company, nom='Commercial')
        sans = [c for c in com.permissions if c != CODE]
        resp = api.patch(f'/api/django/roles/{com.id}/',
                         {'permissions': sans}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_migration_aller_retour(self):
        migration = importlib.import_module(
            'apps.roles.migrations.0007_asec9_code_encaisser')
        company = Company.objects.create(nom='ASEC9 c', slug='asec9-migr')
        com = Role.objects.create(
            company=company, nom='Commercial', est_systeme=True,
            permissions=['crm_voir'])
        tech = Role.objects.create(
            company=company, nom='Technicien', est_systeme=True,
            permissions=['sav_voir'])
        perso = Role.objects.create(
            company=company, nom='Vendeur maison', permissions=['crm_voir'])

        migration.ajouter_aux_roles_systeme(django_apps, None)
        for r in (com, tech, perso):
            r.refresh_from_db()
        self.assertEqual(com.permissions, ['crm_voir', CODE])
        self.assertEqual(tech.permissions, ['sav_voir'])
        self.assertEqual(perso.permissions, ['crm_voir'])
        # Idempotente.
        migration.ajouter_aux_roles_systeme(django_apps, None)
        com.refresh_from_db()
        self.assertEqual(com.permissions, ['crm_voir', CODE])

        perso.permissions = ['crm_voir', CODE, 'crm_creer']
        perso.save(update_fields=['permissions'])
        migration.retirer_le_code(django_apps, None)
        com.refresh_from_db()
        perso.refresh_from_db()
        self.assertEqual(com.permissions, ['crm_voir'])
        self.assertEqual(perso.permissions, ['crm_voir', 'crm_creer'])
