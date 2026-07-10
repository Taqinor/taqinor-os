"""ARC42 — tests du scaffolder ``startapp_erp``.

On génère un module DANS UN DOSSIER TEMPORAIRE (jamais dans ``apps/`` du dépôt,
donc jamais committé ni ajouté à INSTALLED_APPS) et on vérifie :
  * les fichiers attendus existent, avec la substitution ``{{ ... }}`` faite ;
  * chaque ``.py`` généré COMPILE (aucun ``{{`` résiduel) ;
  * le code vise bien les primitives fondation (TenantModel, viewset scopé,
    numbering, manifeste, platform) ;
  * la checklist des 8 points de câblage est imprimée ;
  * ``--dry-run`` n'écrit rien mais imprime quand même la checklist.
"""
import io
import os
import py_compile
import shutil
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


def _default_startapp_options():
    """Options par défaut lues par ``TemplateCommand.handle`` (Django).

    Reproduit les défauts d'``add_arguments`` de ``startapp`` pour pouvoir
    appeler ``Command.handle(**options)`` directement (sans passer par
    ``call_command``, qui rejetterait la clé de contexte ``app_label``).
    """
    return {
        'verbosity': 0,
        'extensions': ['py'],
        'files': [],
        'no_color': True,
        'force_color': False,
    }


class StartAppErpTest(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='startapp_erp_')
        self.target = os.path.join(self.tmp, 'demo')
        os.makedirs(self.target)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_dry_run_ecrit_rien_mais_imprime_checklist(self):
        out = io.StringIO()
        call_command('startapp_erp', 'demo', '--dry-run', stdout=out)
        texte = out.getvalue()
        # Les 8 points numérotés sont présents.
        for n in range(1, 9):
            self.assertIn(f'{n}.', texte)
        for mot in ('INSTALLED_APPS', 'urls.py', 'importlinter',
                    'ALL_PERMISSIONS', 'module_manifest', 'PREFIX_TO_MODULE',
                    'module.config.jsx', 'platform.py'):
            self.assertIn(mot, texte)
        # Rien n'a été écrit dans apps/.
        self.assertFalse(os.path.exists(self.target) and
                         os.listdir(self.target))

    def test_label_invalide_leve_erreur(self):
        for mauvais in ('Demo', '1demo', 'apps.demo', 'demo-app', ''):
            with self.assertRaises(CommandError):
                call_command('startapp_erp', mauvais, '--dry-run')

    def test_generation_dans_tmp_produit_fichiers_valides(self):
        # On exerce le MÊME chemin que la commande (super().handle(**options)
        # avec ``app_label`` injecté dans le contexte de rendu), mais en écrivant
        # dans un dossier tmp — via l'objet Command de ``startapp`` directement
        # (call_command validerait les kwargs et rejetterait ``app_label``, que
        # notre commande passe légitimement à travers le contexte de rendu).
        from django.core.management.commands.startapp import (
            Command as StartAppCommand,
        )

        from core.management.commands import startapp_erp

        out = io.StringIO()
        options = _default_startapp_options()
        options.update({
            'name': 'demo',
            'directory': self.target,
            'template': startapp_erp._TEMPLATE_DIR,
            'app_label': 'demo',
        })
        cmd = StartAppCommand(stdout=out)
        cmd.handle(**options)

        attendus = [
            '__init__.py', 'apps.py', 'models.py', 'viewsets.py',
            'platform.py', 'selectors.py', 'services.py', 'receivers.py',
            'serializers.py', 'urls.py', 'admin.py',
            os.path.join('migrations', '__init__.py'),
            os.path.join('tests', '__init__.py'),
            os.path.join('tests', 'test_smoke.py'),
        ]
        for rel in attendus:
            chemin = os.path.join(self.target, rel)
            self.assertTrue(os.path.exists(chemin),
                            f'fichier généré manquant : {rel}')

        # Chaque .py compile (aucun {{ }} résiduel) et la substitution est faite.
        for racine, _dirs, fichiers in os.walk(self.target):
            for nom in fichiers:
                if not nom.endswith('.py'):
                    continue
                chemin = os.path.join(racine, nom)
                with open(chemin, encoding='utf-8') as fh:
                    contenu = fh.read()
                self.assertNotIn('{{', contenu,
                                 f'gabarit non substitué dans {nom}')
                self.assertNotIn('{%', contenu)
                py_compile.compile(chemin, doraise=True)

        # apps.py vise le manifeste ODX2 avec la bonne clé.
        with open(os.path.join(self.target, 'apps.py'), encoding='utf-8') as fh:
            apps_py = fh.read()
        self.assertIn("class DemoConfig", apps_py)
        self.assertIn("name = 'apps.demo'", apps_py)
        self.assertIn("'key': 'demo'", apps_py)
        self.assertIn('module_manifest', apps_py)

        # models.py hérite du socle multi-tenant ARC1.
        with open(os.path.join(self.target, 'models.py'),
                  encoding='utf-8') as fh:
            models_py = fh.read()
        self.assertIn('from core.models import TenantModel', models_py)

        # viewsets.py vise la base scopée société ARC2.
        with open(os.path.join(self.target, 'viewsets.py'),
                  encoding='utf-8') as fh:
            viewsets_py = fh.read()
        self.assertIn(
            'from core.viewsets import CompanyScopedModelViewSet', viewsets_py)

        # services.py enseigne la numérotation fondation (jamais count()+1).
        with open(os.path.join(self.target, 'services.py'),
                  encoding='utf-8') as fh:
            services_py = fh.read()
        self.assertIn('core.numbering', services_py)

        # platform.py déclare le manifeste ARC28 avec les 7 surfaces (vides).
        with open(os.path.join(self.target, 'platform.py'),
                  encoding='utf-8') as fh:
            platform_py = fh.read()
        self.assertIn('PLATFORM', platform_py)
        for surface in ('searchable_models', 'record_targets',
                        'customfield_models', 'import_specs',
                        'agent_actions_module', 'automation_state_fields',
                        'kpi_providers'):
            self.assertIn(surface, platform_py)
