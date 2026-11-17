"""TCH4 — socle de l'app `taches` : manifeste collecté, non installable, sans base."""
from django.conf import settings
from django.test import SimpleTestCase

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
