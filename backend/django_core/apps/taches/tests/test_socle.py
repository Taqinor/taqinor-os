"""TCH4 — socle de l'app `taches` : manifeste collecté (installable depuis TCH131), sans base ; TCH5 — `taches_voir`
porté par aucun rôle système (catalogue, et en base après `init_roles`) ; TCH130 — activation : porté par
le SEUL rôle système « Administrateur » ; TCH168 — et par « Directeur », le rôle où `init_roles` range le
propriétaire."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from core.modules import collect_manifests


class SocleTachesTests(SimpleTestCase):
    def test_app_installee(self):
        self.assertIn('apps.taches', settings.INSTALLED_APPS)

    def test_manifeste_collecte_installable_a_l_activation(self):
        # TCH131 — activation : le module devient installable (il ne l'était pas avant, TCH4).
        manifeste = collect_manifests().get('taches')
        self.assertIsNotNone(manifeste, 'manifeste « taches » non collecté')
        self.assertTrue(manifeste['installable'])
        self.assertEqual(manifeste['app_label'], 'taches')

    def test_reglage_siri_declare(self):
        self.assertTrue(hasattr(settings, 'TACHES_RACCOURCI_SIRI_URL'))
        self.assertIsInstance(settings.TACHES_RACCOURCI_SIRI_URL, str)

    def test_platform_sans_surface(self):
        from apps.taches.platform import PLATFORM
        self.assertEqual(PLATFORM['module'], 'taches')
        # TCH111 : seule surface câblée, les actions du Copilote.
        self.assertEqual(PLATFORM['agent_actions_module'], 'apps.taches.agent_actions')
        for cle, valeur in PLATFORM.items():
            if cle not in ('module', 'agent_actions_module'):
                self.assertFalse(valeur, cle)

    def test_aucun_admin(self):
        from pathlib import Path
        racine = Path(__file__).resolve().parent.parent
        self.assertFalse((racine / 'admin.py').exists())


class DroitTachesVoirTests(SimpleTestCase):
    """TCH5 — `taches_voir` déclaré ; TCH130 puis TCH168 — porté par les rôles système Directeur et
    Administrateur, aucun autre (invariant 28)."""

    def test_droit_declare_en_fin_de_catalogue(self):
        from apps.roles.permissions_registre import ALL_PERMISSIONS, PERMISSION_MODULE
        self.assertEqual(ALL_PERMISSIONS.count('taches_voir'), 1)
        self.assertEqual(PERMISSION_MODULE.get('taches_voir'), 'taches')

    def test_directeur_et_administrateur_le_portent_seuls(self):
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        porteurs = [nom for nom, permissions in CANONICAL_SYSTEM_ROLES
                    if 'taches_voir' in permissions]
        self.assertEqual(porteurs, ['Directeur', 'Administrateur'])


class InitRolesTachesVoirTests(TestCase):
    """Mineur 2 de la revue F1, mis à jour par TCH130 puis TCH168 — après `init_roles` (rôles système semés,
    comptes hérités et superutilisateur rattachés), SEULES les lignes `Role` « Directeur » et « Administrateur »
    portent `taches_voir` ; le superutilisateur, que `init_roles` range « Directeur », a donc le droit."""

    def test_seuls_directeur_et_administrateur_en_base_le_portent(self):
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
        self.assertEqual(sorted(r.nom for r in roles if 'taches_voir' in (r.permissions or [])),
                         ['Administrateur', 'Directeur'])
        superutilisateur = utilisateurs.select_related('role').get(username='su@taches-init-roles')
        self.assertEqual(superutilisateur.role.nom, 'Directeur')
        self.assertTrue(superutilisateur.has_erp_permission('taches_voir'))
