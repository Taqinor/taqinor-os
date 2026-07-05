"""Tests YOPSB12 — détecteur N+1 (nplusone) dev-only, jamais en prod/CI.

Couvre : le module ``erp_agentique.settings.dev`` se charge SANS exception
même quand ``nplusone`` n'est pas installé (import gardé — CI n'installe
QUE requirements.txt, jamais requirements-dev.txt), et
``erp_agentique.settings.prod``/``base`` n'y font JAMAIS référence."""
import importlib
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[4]


class NplusoneDevOnlyTests(SimpleTestCase):
    def test_dev_settings_load_without_raising(self):
        """settings.dev DOIT toujours se charger sans exception, que
        nplusone soit installé ou non (import gardé try/except ImportError).
        Le process de test CI n'a PAS nplusone installé (requirements-dev.txt
        n'est jamais installé par ci.yml) — ce test s'exécute donc déjà dans
        le cas réel « paquet absent »."""
        import erp_agentique.settings.dev as dev_settings
        try:
            importlib.reload(dev_settings)
        except ImportError:
            self.fail(
                'settings.dev ne doit JAMAIS lever si nplusone est absent '
                '(import gardé requis pour CI/prod).')

    def test_prod_settings_never_reference_nplusone(self):
        settings_dir = ROOT / 'backend' / 'django_core' / 'erp_agentique' / 'settings'
        prod_source = (settings_dir / 'prod.py').read_text(encoding='utf-8')
        self.assertNotIn('nplusone', prod_source)

    def test_base_settings_never_reference_nplusone(self):
        settings_dir = ROOT / 'backend' / 'django_core' / 'erp_agentique' / 'settings'
        base_source = (settings_dir / 'base.py').read_text(encoding='utf-8')
        self.assertNotIn('nplusone', base_source)

    def test_requirements_txt_never_lists_nplusone(self):
        """requirements.txt (installé en CI/prod) ne doit JAMAIS lister
        nplusone — seul requirements-dev.txt (jamais installé par CI) le
        fait."""
        django_core_dir = ROOT / 'backend' / 'django_core'
        req = (django_core_dir / 'requirements.txt').read_text(
            encoding='utf-8')
        self.assertNotIn('nplusone', req)

    def test_requirements_dev_txt_lists_nplusone(self):
        django_core_dir = ROOT / 'backend' / 'django_core'
        req_dev = (django_core_dir / 'requirements-dev.txt').read_text(
            encoding='utf-8')
        self.assertIn('nplusone', req_dev)
