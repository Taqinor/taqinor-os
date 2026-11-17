"""TCH4 — socle de l'app `taches` : manifeste collecté, non installable, sans base ; TCH5 — `taches_voir`
porté par aucun rôle système (catalogue, et en base après `init_roles`)."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from core.modules import collect_manifests


class SocleTachesTests(SimpleTestCase):
    def test_app_installee(self):
        self.assertIn('apps.taches', settings.INSTALLED_APPS)

    def test_manifeste_collecte_non_installable(self):
        manifeste = collect_manifests().get('taches')
        self.assertIsNotNone(manifeste, 'manifeste « taches » non collecté')
        self.assertFalse(manifeste['installable'])
        self.assertEqual(manifeste['app_label'], 'taches')

    def test_reglage_siri_declare(self):
        self.assertTrue(hasattr(settings, 'TACHES_RACCOURCI_SIRI_URL'))
        self.assertIsInstance(settings.TACHES_RACCOURCI_SIRI_URL, str)

    def test_platform_sans_surface(self):
        from apps.taches.platform import PLATFORM
        self.assertEqual(PLATFORM['module'], 'taches')
        for cle, valeur in PLATFORM.items():
            if cle != 'module':
                self.assertFalse(valeur, cle)

    def test_aucun_admin(self):
        from pathlib import Path
        racine = Path(__file__).resolve().parent.parent
        self.assertFalse((racine / 'admin.py').exists())


class DroitTachesVoirTests(SimpleTestCase):
    """TCH5 — `taches_voir` déclaré, porté par AUCUN rôle système (invariant 28)."""

    def test_droit_declare_en_fin_de_catalogue(self):
        from apps.roles.permissions_registre import ALL_PERMISSIONS, PERMISSION_MODULE
        self.assertEqual(ALL_PERMISSIONS.count('taches_voir'), 1)
        self.assertEqual(PERMISSION_MODULE.get('taches_voir'), 'taches')

    def test_aucun_role_systeme_ne_le_porte(self):
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        porteurs = [nom for nom, permissions in CANONICAL_SYSTEM_ROLES
                    if 'taches_voir' in permissions]
        self.assertEqual(porteurs, [])


class InitRolesSansTachesVoirTests(TestCase):
    """Mineur 2 de la revue F1 — après `init_roles` (rôles système semés, comptes hérités et
    superutilisateur rattachés), AUCUNE ligne `Role` en base ne porte `taches_voir`."""

    def test_aucun_role_en_base_ne_le_porte(self):
        from apps.roles.models import Role
        from authentication.models import Company
        societe = Company.objects.create(nom='Init rôles tâches', slug='taches-init-roles')
        utilisateurs = get_user_model().objects
        for palier in ('admin', 'responsable', 'normal'):
            utilisateurs.create_user(username=f'{palier}@taches-init-roles', password=None,
                                     company=societe, role_legacy=palier)
        utilisateurs.create_superuser(username='su@taches-init-roles', password=None, company=societe)
        call_command('init_roles', verbosity=0)
        roles = list(Role.objects.filter(company=societe))
        self.assertTrue(roles, 'init_roles n\'a semé aucun rôle')
        self.assertEqual([r.nom for r in roles if 'taches_voir' in (r.permissions or [])], [])
