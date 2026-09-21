"""NTEXT14 — installation / désinstallation d'un package par tenant.

Couvre : la matérialisation RÉELLE du manifest en objets scopés société,
l'idempotence (ré-installer ne duplique rien), l'absence d'orphelin après
désinstallation, la non-suppression des objets PRÉEXISTANTS (données de
l'utilisateur), l'isolation société, et le registre de matérialiseurs (une
section sans matérialiseur est simplement ignorée).
"""
import itertools

from django.test import TestCase

from authentication.models import Company
from core.models import BrandedTemplate

from apps.extensions import services
from apps.extensions.models import ExtensionInstall, ExtensionPackage

_seq = itertools.count(1)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT14 Co {next(_seq)}')


def make_package(**kwargs):
    n = next(_seq)
    kwargs.setdefault('code', f'ntext14-pkg-{n}')
    kwargs.setdefault('nom', f'Package NTEXT14 {n}')
    kwargs.setdefault('manifest', {
        'branded_templates': [
            {'kind': 'email', 'code': 'relance_ext',
             'nom': 'Relance (extension)', 'sujet': 'Relance',
             'corps': 'Bonjour {{ client }}'},
            {'kind': 'email', 'code': 'merci_ext', 'nom': 'Merci'},
        ],
    })
    return ExtensionPackage.objects.create(**kwargs)


class InstallationTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT14 Install')
        self.package = make_package()

    def test_install_materialises_the_manifest_into_real_objects(self):
        install = services.installer_package(self.company, self.package)

        self.assertEqual(install.statut, ExtensionInstall.Statut.INSTALLE)
        self.assertEqual(install.company, self.company)
        self.assertEqual(install.version, self.package.version)
        self.assertIsNotNone(install.installe_le)
        self.assertEqual(len(install.objets_crees), 2)

        modeles = BrandedTemplate.objects.filter(company=self.company)
        self.assertEqual(modeles.count(), 2)
        relance = modeles.get(code='relance_ext')
        self.assertEqual(relance.nom, 'Relance (extension)')
        self.assertEqual(relance.corps, 'Bonjour {{ client }}')
        self.assertIn(f'core.brandedtemplate:{relance.pk}',
                      install.objets_crees)

    def test_reinstalling_is_idempotent(self):
        premier = services.installer_package(self.company, self.package)
        second = services.installer_package(self.company, self.package)

        self.assertEqual(premier.pk, second.pk)
        self.assertEqual(ExtensionInstall.objects.count(), 1)
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 2)
        self.assertEqual(sorted(second.objets_crees),
                         sorted(premier.objets_crees))

    def test_install_is_scoped_to_its_company(self):
        autre = make_company('NTEXT14 Autre')
        services.installer_package(self.company, self.package)
        services.installer_package(autre, self.package)

        self.assertEqual(ExtensionInstall.objects.count(), 2)
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 2)
        self.assertEqual(
            BrandedTemplate.objects.filter(company=autre).count(), 2)

    def test_unknown_section_is_ignored_without_error(self):
        package = make_package(manifest={
            'automation_rules': [{'nom': 'Pas encore branché'}],
            'section_inconnue': [{'x': 1}],
            'branded_templates': [{'kind': 'email', 'code': 'seul'}],
        })
        install = services.installer_package(self.company, package)
        self.assertEqual(install.statut, ExtensionInstall.Statut.INSTALLE)
        self.assertEqual(len(install.objets_crees), 1)

    def test_malformed_manifest_section_never_raises(self):
        package = make_package(manifest={'branded_templates': 'pas une liste'})
        install = services.installer_package(self.company, package)
        self.assertEqual(install.objets_crees, [])

    def test_definition_without_code_is_skipped(self):
        package = make_package(manifest={
            'branded_templates': [{'kind': 'email', 'nom': 'Sans code'}]})
        install = services.installer_package(self.company, package)
        self.assertEqual(install.objets_crees, [])
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 0)


class DesinstallationTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT14 Desinstall')
        self.package = make_package()

    def test_uninstall_leaves_no_orphan(self):
        install = services.installer_package(self.company, self.package)
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 2)

        install = services.desinstaller_package(install)

        self.assertEqual(install.statut, ExtensionInstall.Statut.DESINSTALLE)
        self.assertEqual(install.objets_crees, [])
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 0)

    def test_uninstall_never_removes_a_preexisting_user_object(self):
        # L'utilisateur avait DÉJÀ créé « relance_ext » avec son propre texte.
        sien = BrandedTemplate.objects.create(
            company=self.company, kind='email', code='relance_ext',
            nom='Ma relance à moi', corps='Texte saisi par l’utilisateur')

        install = services.installer_package(self.company, self.package)
        # L'objet préexistant est REPRIS tel quel, jamais écrasé…
        sien.refresh_from_db()
        self.assertEqual(sien.nom, 'Ma relance à moi')
        # …et n'est pas compté comme posé par l'installation.
        self.assertEqual(len(install.objets_crees), 1)
        self.assertNotIn(f'core.brandedtemplate:{sien.pk}',
                         install.objets_crees)

        services.desinstaller_package(install)

        # …donc il SURVIT à la désinstallation, avec son texte intact.
        sien.refresh_from_db()
        self.assertEqual(sien.corps, 'Texte saisi par l’utilisateur')
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 1)

    def test_uninstall_never_touches_another_company(self):
        autre = make_company('NTEXT14 Desinstall Autre')
        install = services.installer_package(self.company, self.package)
        install_autre = services.installer_package(autre, self.package)

        services.desinstaller_package(install)

        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            BrandedTemplate.objects.filter(company=autre).count(), 2)
        install_autre.refresh_from_db()
        self.assertEqual(install_autre.statut,
                         ExtensionInstall.Statut.INSTALLE)

    def test_reinstall_after_uninstall_recreates_everything(self):
        install = services.installer_package(self.company, self.package)
        services.desinstaller_package(install)
        install = services.installer_package(self.company, self.package)

        self.assertEqual(install.statut, ExtensionInstall.Statut.INSTALLE)
        self.assertEqual(len(install.objets_crees), 2)
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 2)

    def test_uninstall_is_idempotent(self):
        install = services.installer_package(self.company, self.package)
        services.desinstaller_package(install)
        services.desinstaller_package(install)
        self.assertEqual(install.objets_crees, [])
        self.assertEqual(
            BrandedTemplate.objects.filter(company=self.company).count(), 0)


class RegistreTests(TestCase):
    def test_branded_templates_materializer_is_registered_natively(self):
        self.assertIn('branded_templates', services.materializers())

    def test_registering_requires_a_section_and_a_callable(self):
        with self.assertRaises(ValueError):
            services.register_materializer('', lambda c, d: (None, False))
        with self.assertRaises(ValueError):
            services.register_materializer('x', None)

    def test_a_failing_materializer_marks_the_install_in_error(self):
        def _casse(company, definition):
            raise RuntimeError('boom')

        services.register_materializer('section_qui_casse', _casse)
        try:
            company = make_company('NTEXT14 Erreur')
            package = make_package(manifest={
                'section_qui_casse': [{'x': 1}],
                'branded_templates': [{'kind': 'email', 'code': 'quand_meme'}],
            })
            install = services.installer_package(company, package)
            self.assertEqual(install.statut, ExtensionInstall.Statut.ERREUR)
            # La section saine a quand même été matérialisée.
            self.assertEqual(len(install.objets_crees), 1)
        finally:
            services._MATERIALIZERS.pop('section_qui_casse', None)
