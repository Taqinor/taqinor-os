"""Tests XPAI7 — Permissions paie dédiées `paie_voir`/`paie_gerer`.

Couvre : un rôle avec ``paie_voir`` SEUL lit (GET) mais ne peut ni calculer ni
clôturer (POST → 403) ; sans aucune permission paie → 403 même en lecture ;
un rôle avec ``paie_gerer`` peut écrire ; un compte legacy SANS rôle fin garde
l'accès Responsable/Admin historique ; ``init_roles`` reste idempotent et
accorde ``paie_voir``/``paie_gerer`` à Directeur/Administrateur/Responsable.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APIClient

from authentication.models import Company
from apps.paie.models import PeriodePaie
from apps.paie.services import ensure_defaults
from apps.roles.models import ALL_PERMISSIONS, Role

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def _client_for(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class PaieVoirOuGererTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai7-perm')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_paie_voir_seul_lit_mais_ne_calcule_pas(self):
        role = Role.objects.create(
            company=self.co, nom='Lecteur paie', permissions=['paie_voir'])
        user = User.objects.create_user(
            username='lecteur', password='x', role=role, company=self.co)
        api = _client_for(user)

        resp = api.get('/api/django/paie/periodes/')
        self.assertEqual(resp.status_code, 200)

        resp = api.post(
            f'/api/django/paie/periodes/{self.periode.id}/changer-statut/',
            {'statut': 'calculee'}, format='json')
        self.assertEqual(resp.status_code, 403)

        resp = api.post(
            f'/api/django/paie/periodes/{self.periode.id}/cloturer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_sans_permission_paie_403_meme_en_lecture(self):
        role = Role.objects.create(
            company=self.co, nom='Sans paie', permissions=['stock_voir'])
        user = User.objects.create_user(
            username='sanspaie', password='x', role=role, company=self.co)
        api = _client_for(user)

        resp = api.get('/api/django/paie/periodes/')
        self.assertEqual(resp.status_code, 403)

    def test_paie_gerer_peut_ecrire(self):
        role = Role.objects.create(
            company=self.co, nom='Gestionnaire paie',
            permissions=['paie_voir', 'paie_gerer'])
        user = User.objects.create_user(
            username='gestionnaire', password='x', role=role, company=self.co)
        api = _client_for(user)

        resp = api.post(
            f'/api/django/paie/periodes/{self.periode.id}/changer-statut/',
            {'statut': 'calculee'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_paie_gerer_seul_sans_voir_peut_quand_meme_ecrire(self):
        # paie_gerer gouverne les écritures ; l'absence de paie_voir ne
        # bloque QUE les méthodes safe (GET), pas les actions d'écriture.
        role = Role.objects.create(
            company=self.co, nom='Gerer seul', permissions=['paie_gerer'])
        user = User.objects.create_user(
            username='gererseul', password='x', role=role, company=self.co)
        api = _client_for(user)

        resp = api.post(
            f'/api/django/paie/periodes/{self.periode.id}/changer-statut/',
            {'statut': 'calculee'}, format='json')
        self.assertEqual(resp.status_code, 200)
        resp = api.get('/api/django/paie/periodes/')
        self.assertEqual(resp.status_code, 403)

    def test_compte_legacy_sans_role_garde_acces_responsable(self):
        # Repli historique : un compte legacy SANS role fin (role_legacy
        # responsable/admin) garde l'accès complet — aucune régression.
        user = User.objects.create_user(
            username='legacy_resp', password='x', role_legacy='responsable',
            company=self.co)
        api = _client_for(user)

        resp = api.get('/api/django/paie/periodes/')
        self.assertEqual(resp.status_code, 200)
        resp = api.post(
            f'/api/django/paie/periodes/{self.periode.id}/changer-statut/',
            {'statut': 'calculee'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_compte_legacy_utilisateur_normal_refuse(self):
        user = User.objects.create_user(
            username='legacy_normal', password='x', role_legacy='normal',
            company=self.co)
        api = _client_for(user)
        resp = api.get('/api/django/paie/periodes/')
        self.assertEqual(resp.status_code, 403)


class InitRolesPaieTests(TestCase):
    def test_init_roles_accorde_paie_a_directeur_admin_responsable(self):
        make_company('xpai7-init')
        call_command('init_roles')
        for nom in ('Directeur', 'Administrateur', 'Responsable'):
            role = Role.objects.filter(nom=nom).first()
            self.assertIsNotNone(role, f'Rôle {nom} absent')
            self.assertIn('paie_voir', role.permissions)
            self.assertIn('paie_gerer', role.permissions)

    def test_init_roles_idempotent(self):
        make_company('xpai7-idem')
        call_command('init_roles')
        call_command('init_roles')
        roles = Role.objects.filter(nom='Directeur')
        self.assertEqual(roles.count(), 1)
        self.assertIn('paie_gerer', roles.first().permissions)

    def test_paie_voir_gerer_dans_all_permissions(self):
        self.assertIn('paie_voir', ALL_PERMISSIONS)
        self.assertIn('paie_gerer', ALL_PERMISSIONS)
