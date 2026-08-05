"""NTADM21 — garde-fou de la délégation (`Role.perimetre`).

Un acteur dont le rôle porte un périmètre ne peut ni fabriquer, ni éditer, ni
assigner un rôle qui sort de ce périmètre (403). Directeur/Administrateur
(périmètre nul) restent strictement inchangés.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import (
    PERIMETRE_RH,
    PERIMETRE_VENTES,
    ROLE_ADMIN_RH,
    ROLE_ADMIN_VENTES,
    Role,
    perimetre_de,
    permissions_hors_perimetre,
)

User = get_user_model()


def _company(nom, slug):
    """Nom ET slug EXPLICITEMENT distincts (le slug est UNIQUE)."""
    return Company.objects.create(nom=nom, slug=slug)


class Ntadm21FonctionsPuresTests(TestCase):
    def test_perimetre_nul_ne_restreint_rien(self):
        self.assertEqual(
            permissions_hors_perimetre(None, ['ventes_creer', 'paie_gerer']),
            [])

    def test_permissions_hors_perimetre_listees_triees(self):
        self.assertEqual(
            permissions_hors_perimetre(
                PERIMETRE_RH, ['paie_gerer', 'ventes_creer', 'crm_creer']),
            ['crm_creer', 'ventes_creer'])

    def test_marqueurs_de_restriction_toujours_admis(self):
        """Un marqueur qui RÉDUIT un rôle n'en sort jamais le périmètre."""
        self.assertEqual(
            permissions_hors_perimetre(
                PERIMETRE_VENTES,
                ['records_scope_equipe', 'app_crm_voir', 'ventes_voir']),
            [])

    def test_perimetre_de_un_compte_sans_role_est_global(self):
        company = _company('NTADM21 Pur Co', 'ntadm21-pur-co')
        user = User.objects.create_user(
            username='ntadm21_legacy', password='pw', company=company,
            role_legacy='admin')
        self.assertIsNone(perimetre_de(user))


class Ntadm21SeedingTests(TestCase):
    def setUp(self):
        self.company = _company('NTADM21 Seed Co', 'ntadm21-seed-co')
        call_command('init_roles')

    def test_les_admins_delegues_portent_leur_perimetre(self):
        self.assertEqual(
            Role.objects.get(
                company=self.company, nom=ROLE_ADMIN_RH).perimetre,
            PERIMETRE_RH)
        self.assertEqual(
            Role.objects.get(
                company=self.company, nom=ROLE_ADMIN_VENTES).perimetre,
            PERIMETRE_VENTES)

    def test_les_roles_historiques_restent_globaux(self):
        for nom in ('Directeur', 'Administrateur', 'Commercial', 'Viewer'):
            self.assertIsNone(
                Role.objects.get(company=self.company, nom=nom).perimetre,
                nom)


class Ntadm21GardeApiTests(TestCase):
    def setUp(self):
        self.company = _company('NTADM21 API Co', 'ntadm21-api-co')
        call_command('init_roles')
        self.role_rh = Role.objects.get(
            company=self.company, nom=ROLE_ADMIN_RH)
        self.role_ventes = Role.objects.get(
            company=self.company, nom=ROLE_ADMIN_VENTES)
        self.role_directeur = Role.objects.get(
            company=self.company, nom='Directeur')

        # Rôle personnalisé GLOBAL (hors périmètre RH) servant de cible.
        self.role_custom_ventes = Role.objects.create(
            company=self.company, nom='Vendeur maison',
            permissions=['ventes_voir', 'ventes_creer'])

        self.admin_rh = User.objects.create_user(
            username='ntadm21_rh', password='pw', company=self.company,
            role=self.role_rh, role_legacy='responsable')
        self.directeur = User.objects.create_user(
            username='ntadm21_dir', password='pw', company=self.company,
            role=self.role_directeur, role_legacy='admin')
        self.cible = User.objects.create_user(
            username='ntadm21_cible', password='pw', company=self.company,
            role_legacy='normal')

        self.api_rh = APIClient()
        self.api_rh.force_authenticate(self.admin_rh)
        self.api_dir = APIClient()
        self.api_dir.force_authenticate(self.directeur)

    # ── Création de rôle ───────────────────────────────────────────────────
    def test_delegue_cree_un_role_dans_son_perimetre(self):
        resp = self.api_rh.post(
            '/api/django/roles/',
            {'nom': 'Assistant paie',
             'permissions': ['paie_voir', 'users_voir']},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cree = Role.objects.get(company=self.company, nom='Assistant paie')
        # Le rôle créé HÉRITE du périmètre de son créateur : impossible de
        # fabriquer un rôle « global » pour s'échapper.
        self.assertEqual(cree.perimetre, PERIMETRE_RH)

    def test_delegue_ne_cree_pas_un_role_hors_perimetre(self):
        resp = self.api_rh.post(
            '/api/django/roles/',
            {'nom': 'Faux vendeur', 'permissions': ['ventes_creer']},
            format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(
            Role.objects.filter(
                company=self.company, nom='Faux vendeur').exists())

    def test_delegue_n_edite_pas_un_role_hors_perimetre(self):
        resp = self.api_rh.patch(
            f'/api/django/roles/{self.role_custom_ventes.id}/',
            {'permissions': ['paie_voir']}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.role_custom_ventes.refresh_from_db()
        self.assertEqual(
            self.role_custom_ventes.permissions,
            ['ventes_voir', 'ventes_creer'])

    # ── Assignation de rôle ────────────────────────────────────────────────
    def test_delegue_n_assigne_pas_un_role_hors_perimetre(self):
        resp = self.api_rh.patch(
            f'/api/django/users/{self.cible.id}/',
            {'role': self.role_custom_ventes.id}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.cible.refresh_from_db()
        self.assertIsNone(self.cible.role_id)

    def test_delegue_assigne_un_role_de_son_perimetre(self):
        resp = self.api_rh.patch(
            f'/api/django/users/{self.cible.id}/',
            {'role': self.role_rh.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cible.refresh_from_db()
        self.assertEqual(self.cible.role_id, self.role_rh.id)

    # ── Non-régression : le périmètre GLOBAL est inchangé ──────────────────
    def test_directeur_assigne_n_importe_quel_role(self):
        resp = self.api_dir.patch(
            f'/api/django/users/{self.cible.id}/',
            {'role': self.role_custom_ventes.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_directeur_edite_n_importe_quel_role(self):
        resp = self.api_dir.patch(
            f'/api/django/roles/{self.role_custom_ventes.id}/',
            {'permissions': ['ventes_voir']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_directeur_cree_un_role_sans_perimetre_impose(self):
        resp = self.api_dir.post(
            '/api/django/roles/',
            {'nom': 'Rôle global', 'permissions': ['crm_voir', 'paie_voir']},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(
            Role.objects.get(
                company=self.company, nom='Rôle global').perimetre)
