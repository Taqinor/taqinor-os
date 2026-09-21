"""NTEXT15 — dépendances + compatibilité de version d'un package.

Le manifest porte ``depends`` (clés de modules ``core.modules`` requis) +
``min_version``. ``installer_package`` refuse (``PackageIncompatible``,
erreur FR, AUCUN effet de bord) si un module requis est désactivé pour la
société, ou si une install ANTÉRIEURE de ce package est d'une version
incompatible avec ``min_version``.
"""
import itertools

from django.test import TestCase

from authentication.models import Company
from core.models import ModuleToggle

from apps.extensions import services
from apps.extensions.models import ExtensionInstall, ExtensionPackage

_seq = itertools.count(1)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT15 Co {next(_seq)}')


def make_package(**kwargs):
    n = next(_seq)
    kwargs.setdefault('code', f'ntext15-pkg-{n}')
    kwargs.setdefault('nom', f'Package NTEXT15 {n}')
    kwargs.setdefault('manifest', {})
    return ExtensionPackage.objects.create(**kwargs)


class DependanceModuleTests(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_module_requis_desactive_refuse_avec_erreur_nommee(self):
        ModuleToggle.objects.create(
            company=self.company, module='sav', actif=False)
        package = make_package(manifest={'depends': ['sav']})

        with self.assertRaises(services.PackageIncompatible) as ctx:
            services.installer_package(self.company, package)
        self.assertIn('sav', str(ctx.exception))
        self.assertFalse(
            ExtensionInstall.objects.filter(
                company=self.company, package=package).exists())

    def test_module_requis_actif_installe_normalement(self):
        ModuleToggle.objects.create(
            company=self.company, module='sav', actif=True)
        package = make_package(manifest={'depends': ['sav']})

        install = services.installer_package(self.company, package)
        self.assertEqual(install.statut, ExtensionInstall.Statut.INSTALLE)

    def test_module_sans_ligne_toggle_est_actif_par_defaut(self):
        """Sans ModuleToggle du tout, un module est actif par défaut
        (core.feature_flags.module_actif) : la dépendance est satisfaite."""
        package = make_package(manifest={'depends': ['sav']})
        install = services.installer_package(self.company, package)
        self.assertEqual(install.statut, ExtensionInstall.Statut.INSTALLE)

    def test_plusieurs_modules_manquants_tous_nommes(self):
        ModuleToggle.objects.create(
            company=self.company, module='sav', actif=False)
        ModuleToggle.objects.create(
            company=self.company, module='flotte', actif=False)
        package = make_package(manifest={'depends': ['sav', 'flotte']})

        with self.assertRaises(services.PackageIncompatible) as ctx:
            services.installer_package(self.company, package)
        self.assertIn('sav', str(ctx.exception))
        self.assertIn('flotte', str(ctx.exception))


class VersionCompatibiliteTests(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_version_installee_trop_ancienne_refusee(self):
        package = make_package(
            version='3.0.0', manifest={'min_version': '2.0.0'})
        ExtensionInstall.objects.create(
            company=self.company, package=package, version='1.0.0',
            statut=ExtensionInstall.Statut.INSTALLE)

        with self.assertRaises(services.PackageIncompatible) as ctx:
            services.installer_package(self.company, package)
        self.assertIn('2.0.0', str(ctx.exception))

    def test_version_installee_compatible_autorisee(self):
        package = make_package(
            version='3.0.0', manifest={'min_version': '2.0.0'})
        ExtensionInstall.objects.create(
            company=self.company, package=package, version='2.5.0',
            statut=ExtensionInstall.Statut.INSTALLE)

        install = services.installer_package(self.company, package)
        self.assertEqual(install.version, '3.0.0')

    def test_sans_install_anterieure_min_version_non_bloquante(self):
        """Une première installation n'a pas d'historique à comparer : la
        contrainte min_version ne s'applique qu'à une MISE À JOUR."""
        package = make_package(
            version='3.0.0', manifest={'min_version': '2.0.0'})
        install = services.installer_package(self.company, package)
        self.assertEqual(install.statut, ExtensionInstall.Statut.INSTALLE)

    def test_sans_min_version_toujours_compatible(self):
        package = make_package(version='9.9.9', manifest={})
        ExtensionInstall.objects.create(
            company=self.company, package=package, version='0.0.1',
            statut=ExtensionInstall.Statut.INSTALLE)
        install = services.installer_package(self.company, package)
        self.assertEqual(install.version, '9.9.9')
