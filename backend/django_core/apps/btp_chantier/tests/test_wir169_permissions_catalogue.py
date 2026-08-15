"""WIR169 — les permissions BTP existent au catalogue ``roles.ALL_PERMISSIONS``.

Défaut constaté : les 8 ViewSets de ``apps.btp_chantier`` déclarent
``read_permission='btp_voir'`` / ``write_permission='btp_gerer'`` et sont gardés
par ``core.permissions.ScopedPermission`` — mais NI ``btp_voir`` NI
``btp_gerer`` n'existaient dans ``roles.ALL_PERMISSIONS``. Comme
``_user_has_or_legacy`` ne fait le repli historique que pour les comptes SANS
rôle fin, tout compte portant un ``Role`` — **Directeur inclus**, qui hérite
pourtant d'``ALL_PERMISSIONS`` — recevait 403 sur la totalité du module.

Ce test verrouille les deux moitiés :
  * un Directeur (rôle fin sur ``DIRECTEUR_PERMISSIONS``) lit ET écrit les
    7 routes BTP ;
  * un rôle fin SANS les codes reste refusé (403) — le durcissement RBAC de
    ces routes n'est pas dilué par la correction.

Pour l'écriture, on n'assemble pas 7 charges utiles valides : on prouve que la
COUCHE PERMISSION passe (un POST vide doit être refusé par la VALIDATION —
400/404 — jamais par la permission — 403).
"""
from django.test import TestCase

from apps.roles.models import (
    ALL_PERMISSIONS, DIRECTEUR_PERMISSIONS, Role,
)

from .helpers import auth, make_company, make_user

BASE = '/api/django/btp-chantier/'

# Les 7 routes de routeur déclarées par ``apps.btp_chantier.urls``.
ROUTES = [
    'reserves-chantier/',
    'rfi/',
    'visas/',
    'journal-chantier/',
    'avenants-chantier/',
    'decomptes-generaux/',
    'diffusions-plan/',
]


class Wir169CatalogueTests(TestCase):
    def test_les_quatre_codes_existent_au_catalogue(self):
        for code in ('btp_voir', 'btp_gerer',
                     'assurances_voir', 'assurances_gerer'):
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_directeur_herite_des_codes_btp(self):
        self.assertIn('btp_voir', DIRECTEUR_PERMISSIONS)
        self.assertIn('btp_gerer', DIRECTEUR_PERMISSIONS)


class Wir169AccesDirecteurTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='wir169-btp', nom='WIR169 BTP')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.directeur = make_user(
            self.company, role='normal', username='wir169-directeur')
        self.directeur.role = self.role_directeur
        self.directeur.save(update_fields=['role'])

        # Rôle fin SANS aucun code BTP (le durcissement doit tenir).
        self.role_nu = Role.objects.create(
            company=self.company, nom='Sans BTP', permissions=['sav_voir'])
        self.sans_droit = make_user(
            self.company, role='normal', username='wir169-sans-droit')
        self.sans_droit.role = self.role_nu
        self.sans_droit.save(update_fields=['role'])

    def test_directeur_lit_les_sept_routes(self):
        api = auth(self.directeur)
        for route in ROUTES:
            with self.subTest(route=route):
                resp = api.get(BASE + route)
                self.assertEqual(resp.status_code, 200, route)

    def test_directeur_passe_la_couche_permission_en_ecriture(self):
        api = auth(self.directeur)
        for route in ROUTES:
            with self.subTest(route=route):
                resp = api.post(BASE + route, {}, format='json')
                # La validation peut refuser (400) — la PERMISSION, non.
                self.assertNotEqual(resp.status_code, 403, route)

    def test_role_fin_sans_code_reste_refuse(self):
        api = auth(self.sans_droit)
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(api.get(BASE + route).status_code, 403, route)
                self.assertEqual(
                    api.post(BASE + route, {}, format='json').status_code,
                    403, route)
