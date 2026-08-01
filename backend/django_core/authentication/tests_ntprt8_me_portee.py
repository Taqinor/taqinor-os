"""Tests NTPRT8 — la PORTÉE du compte est servie (et seulement LUE) par l'API.

Le shell frontend décide de router un compte vers `/portail/<scope>` (ou de le
tenir hors de l'ERP interne) à partir de `portee` + l'id de rattachement servis
par ``/auth/me/``. Deux exigences, la seconde étant la plus importante :

1. `/auth/me/` expose `portee` et les trois `portail_*_id` ;
2. ces champs sont STRICTEMENT en lecture seule : un PATCH — même d'un
   administrateur, même sur son propre profil — ne doit JAMAIS pouvoir
   re-scoper un compte ni le rattacher à une autre entité. Sans cela, une seule
   ligne de corps de requête suffirait à s'auto-rattacher au client d'un tiers.

Run :
    python manage.py test authentication.tests_ntprt8_me_portee -v2
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company, CustomUser


def make_company(slug, nom):
    """Société de test — slug EXPLICITE et DISTINCT par appelant."""
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, permissions):
    role, _ = Role.objects.get_or_create(
        company=company, nom=f'role-{username}',
        defaults={'permissions': list(permissions), 'est_systeme': False})
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)


class MePorteeTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt8-co', 'NTPRT8 Société')
        self.admin = make_user(self.company, 'ntprt8-admin', ['roles_gerer'])
        self.api = APIClient()

    def test_me_expose_la_portee_et_les_ids_de_rattachement(self):
        self.api.force_authenticate(user=self.admin)
        res = self.api.get('/api/django/auth/me/')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['portee'], CustomUser.PORTEE_INTERNE)
        for champ in ('portail_client_id', 'portail_fournisseur_id',
                      'portail_partenaire_id'):
            self.assertIn(champ, res.data)
            self.assertIsNone(res.data[champ])

    def test_me_reflete_une_portee_portail(self):
        portail = make_user(self.company, 'ntprt8-portail', [])
        portail.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        portail.portail_client_id = 42
        portail.save(update_fields=['portee', 'portail_client_id'])

        self.api.force_authenticate(user=portail)
        res = self.api.get('/api/django/auth/me/')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['portee'],
                         CustomUser.PORTEE_PORTAIL_CLIENT)
        self.assertEqual(res.data['portail_client_id'], 42)

    def test_patch_ne_peut_jamais_re_scoper_un_compte(self):
        """Escalade la plus directe possible : se déclarer portail d'un client."""
        cible = make_user(self.company, 'ntprt8-cible', [])
        self.api.force_authenticate(user=self.admin)

        res = self.api.patch(
            f'/api/django/users/{cible.id}/',
            {'portee': CustomUser.PORTEE_PORTAIL_CLIENT,
             'portail_client_id': 99,
             'portail_fournisseur_id': 98,
             'portail_partenaire_id': 97},
            format='json')

        # Le PATCH peut réussir (champs ignorés) mais NE DOIT RIEN changer.
        self.assertIn(res.status_code, (200, 400, 403))
        cible.refresh_from_db()
        self.assertEqual(cible.portee, CustomUser.PORTEE_INTERNE)
        self.assertIsNone(cible.portail_client_id)
        self.assertIsNone(cible.portail_fournisseur_id)
        self.assertIsNone(cible.portail_partenaire_id)
