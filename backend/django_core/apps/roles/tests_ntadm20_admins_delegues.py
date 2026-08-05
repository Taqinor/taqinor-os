"""NTADM20 — rôles d'administration déléguée par domaine (Admin RH / Ventes).

Critère d'acceptation : un « Admin RH » gère les dossiers employés et les
comptes utilisateurs, mais ne voit PAS Paramètres → Société.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

from .models import (
    ADMIN_RH_PERMISSIONS,
    ADMIN_VENTES_PERMISSIONS,
    CANONICAL_SYSTEM_ROLES,
    ROLE_ADMIN_RH,
    ROLE_ADMIN_VENTES,
    Role,
)

User = get_user_model()


def _company(nom, slug):
    """Nom ET slug EXPLICITEMENT distincts (le slug est UNIQUE)."""
    return Company.objects.create(nom=nom, slug=slug)


class Ntadm20ConstantesTests(TestCase):
    """Le contenu des deux presets porte la politique de délégation."""

    def test_les_deux_roles_sont_dans_le_registre_canonique(self):
        noms = [nom for nom, _ in CANONICAL_SYSTEM_ROLES]
        self.assertIn(ROLE_ADMIN_RH, noms)
        self.assertIn(ROLE_ADMIN_VENTES, noms)

    def test_aucun_des_deux_ne_porte_la_cle_d_administration_globale(self):
        for perms in (ADMIN_RH_PERMISSIONS, ADMIN_VENTES_PERMISSIONS):
            self.assertNotIn('roles_gerer', perms)
            self.assertNotIn('parametres_voir', perms)
            self.assertNotIn('parametres_modifier', perms)
            self.assertNotIn('journal_activite_voir', perms)

    def test_admin_rh_ne_touche_ni_crm_ni_ventes_ni_stock(self):
        for code in ADMIN_RH_PERMISSIONS:
            self.assertFalse(
                code.startswith(('crm_', 'ventes_', 'stock_')), code)
        self.assertIn('paie_gerer', ADMIN_RH_PERMISSIONS)
        self.assertIn('salaires_voir', ADMIN_RH_PERMISSIONS)
        self.assertIn('users_gerer', ADMIN_RH_PERMISSIONS)

    def test_admin_ventes_ne_touche_ni_paie_ni_salaires(self):
        for code in ('paie_voir', 'paie_gerer', 'salaires_voir',
                     'users_gerer'):
            self.assertNotIn(code, ADMIN_VENTES_PERMISSIONS)
        self.assertIn('ventes_valider', ADMIN_VENTES_PERMISSIONS)
        self.assertIn('crm_creer', ADMIN_VENTES_PERMISSIONS)

    def test_politique_qg4_preservee_pas_de_stock_creer(self):
        """QG4 : seuls Directeur + Commercial responsable créent un produit."""
        self.assertNotIn('stock_creer', ADMIN_VENTES_PERMISSIONS)
        self.assertNotIn('stock_creer', ADMIN_RH_PERMISSIONS)

    def test_permissions_toutes_connues_du_catalogue(self):
        from .models import ALL_PERMISSIONS
        for code in ADMIN_RH_PERMISSIONS + ADMIN_VENTES_PERMISSIONS:
            self.assertIn(code, ALL_PERMISSIONS, code)


class Ntadm20SeedingTests(TestCase):
    def setUp(self):
        self.company = _company('NTADM20 Co', 'ntadm20-co')

    def test_init_roles_seme_les_deux_roles(self):
        call_command('init_roles')
        for nom in (ROLE_ADMIN_RH, ROLE_ADMIN_VENTES):
            role = Role.objects.get(company=self.company, nom=nom)
            self.assertTrue(role.est_systeme)
            self.assertTrue(role.permissions)

    def test_init_roles_est_idempotent(self):
        call_command('init_roles')
        call_command('init_roles')
        self.assertEqual(
            Role.objects.filter(
                company=self.company, nom=ROLE_ADMIN_RH).count(), 1)

    def test_palier_responsable_jamais_admin(self):
        call_command('init_roles')
        for nom in (ROLE_ADMIN_RH, ROLE_ADMIN_VENTES):
            role = Role.objects.get(company=self.company, nom=nom)
            self.assertEqual(
                CustomUser.tier_for_role(role), CustomUser.ROLE_RESPONSABLE,
                nom)


class Ntadm20AdminRhApiTests(TestCase):
    """Bout en bout : ce que l'Admin RH peut, et ce qu'il ne peut pas."""

    def setUp(self):
        self.company = _company('NTADM20 API Co', 'ntadm20-api-co')
        call_command('init_roles')
        self.role_rh = Role.objects.get(
            company=self.company, nom=ROLE_ADMIN_RH)
        self.user = User.objects.create_user(
            username='ntadm20_rh', password='pw', company=self.company,
            role=self.role_rh, role_legacy='responsable')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_peut_lister_les_dossiers_employes(self):
        resp = self.api.get('/api/django/rh/employes/')
        self.assertEqual(resp.status_code, 200)

    def test_peut_creer_puis_desactiver_un_dossier_employe(self):
        creation = self.api.post(
            '/api/django/rh/employes/',
            {'matricule': 'NTADM20-1', 'nom': 'Alaoui', 'prenom': 'Salma'},
            format='json')
        self.assertEqual(creation.status_code, 201, creation.data)
        sortie = self.api.patch(
            f"/api/django/rh/employes/{creation.data['id']}/",
            {'statut': 'sorti'}, format='json')
        self.assertEqual(sortie.status_code, 200, sortie.data)
        self.assertEqual(sortie.data['statut'], 'sorti')

    def test_peut_atteindre_l_ecran_utilisateurs(self):
        resp = self.api.get('/api/django/users/')
        self.assertEqual(resp.status_code, 200)

    def test_ne_voit_pas_parametres_societe(self):
        """Paramètres → Société reste hors de portée de l'admin délégué."""
        resp = self.api.get('/api/django/companies/')
        self.assertIn(resp.status_code, (401, 403))

    def test_n_est_pas_un_role_administrateur(self):
        self.assertFalse(self.user.is_admin_role)
        self.assertEqual(self.user.menu_tier, CustomUser.ROLE_RESPONSABLE)
