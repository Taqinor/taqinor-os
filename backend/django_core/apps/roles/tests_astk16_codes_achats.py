"""ASTK16 — codes de droits achats/réception/paiement/prix catalogue.

Constat C-ASTK-003 : commander, réceptionner, payer un fournisseur et modifier
un prix catalogue n'avaient AUCUN code octroyable — les vues stock ne
pouvaient donc rien exiger de plus fin que ``stock_*``. Ce module vérifie :

* les 4 codes sont au catalogue (``ALL_PERMISSIONS``), groupés sous le module
  ``stock`` et NON élevés ;
* après ``init_roles`` : Directeur et Administrateur les portent (héritage du
  catalogue), Technicien responsable porte ``achats_receptionner`` seul
  (D-ASTK-3), aucun autre rôle canonique n'en porte ;
* migration ``0006_astk16_codes_achats`` : forwards = zéro titulaire (un rôle
  personnalisé existant ne reçoit rien), backwards = retrait de tout rôle.

Run :
    python manage.py test apps.roles.tests_astk16_codes_achats -v2
"""
import importlib

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import TestCase

from apps.roles.permissions_registre import (
    ALL_PERMISSIONS,
    ELEVATED_PERMISSIONS,
    PERMISSION_MODULE,
)

CODES = (
    'achats_commander', 'achats_receptionner', 'achats_payer',
    'catalogue_prix_modifier',
)

SANS_AUCUN = (
    'Commercial', 'Commercial responsable', 'Commercial terrain',
    'Technicien', 'Viewer', 'Utilisateur',
)


def _company(slug):
    from authentication.models import Company
    return Company.objects.create(slug=slug, nom=slug.upper())


class CodesAchatsTests(TestCase):
    def test_codes_au_catalogue(self):
        for code in CODES:
            with self.subTest(code=code):
                self.assertIn(code, ALL_PERMISSIONS)
                self.assertEqual(ALL_PERMISSIONS.count(code), 1)
                self.assertEqual(PERMISSION_MODULE.get(code), 'stock')
                # Codes d'écriture, pas d'exposition de donnée sensible.
                self.assertNotIn(code, ELEVATED_PERMISSIONS)
                self.assertFalse(code.endswith('_voir'))

    def test_titulaires_par_role_canonique(self):
        from apps.roles.models import Role
        company = _company('astk16-roles')
        call_command('init_roles', verbosity=0)
        roles = {r.nom: list(r.permissions)
                 for r in Role.objects.filter(company=company)}
        for nom in ('Directeur', 'Administrateur'):
            with self.subTest(role=nom):
                for code in CODES:
                    self.assertIn(code, roles[nom])
        tech_resp = roles['Technicien responsable']
        self.assertIn('achats_receptionner', tech_resp)
        for code in ('achats_commander', 'achats_payer',
                     'catalogue_prix_modifier'):
            self.assertNotIn(code, tech_resp)
        for nom in SANS_AUCUN:
            with self.subTest(role=nom):
                self.assertIn(nom, roles)
                self.assertFalse(set(CODES) & set(roles[nom]),
                                 f'{nom} porte un code achats')

    def test_migration_zero_titulaire_et_retour(self):
        from apps.roles.models import Role
        migration = importlib.import_module(
            'apps.roles.migrations.0006_astk16_codes_achats')
        company = _company('astk16-migration')
        perso = Role.objects.create(
            company=company, nom='Acheteur maison',
            permissions=['stock_voir', 'stock_modifier'])

        # forwards : rien n'est écrit — le rôle personnalisé reste intact.
        migration.aucun_titulaire(django_apps, None)
        perso.refresh_from_db()
        self.assertEqual(perso.permissions, ['stock_voir', 'stock_modifier'])

        # backwards : les 4 codes sont retirés de tout rôle, l'ordre des
        # autres codes est préservé.
        perso.permissions = ['stock_voir', 'achats_commander',
                             'stock_modifier', 'catalogue_prix_modifier']
        perso.save(update_fields=['permissions'])
        systeme = Role.objects.create(
            company=company, nom='Directeur maison', est_systeme=False,
            permissions=list(CODES) + ['crm_voir'])
        migration.retirer_les_codes(django_apps, None)
        perso.refresh_from_db()
        systeme.refresh_from_db()
        self.assertEqual(perso.permissions, ['stock_voir', 'stock_modifier'])
        self.assertEqual(systeme.permissions, ['crm_voir'])
