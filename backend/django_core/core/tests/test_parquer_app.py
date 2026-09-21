"""SOLMVP2 — tests de ``manage.py parquer_app`` sur une APP JOUET.

L'app jouet est créée DANS un dossier temporaire (jamais dans ``apps/`` du
dépôt) avec deux modèles liés par une FK et deux vraies migrations, puis
enregistrée le temps du test via ``INSTALLED_APPS``/``BASE_DIR`` surchargés. Le
faux registre (``APPS_PARQUEES``) est injecté par ``mock.patch``. Le dépôt lui
même n'est JAMAIS modifié : urls.py, celery.py et les specs e2e vérifiés sont
des copies synthétiques sous ``BASE_DIR`` temporaire.

Couvert : ordre des ``DeleteModel`` (dépendants d'abord), ``models.py`` vidé,
``apps.py`` minimal (``parked = True``, plus de ``ready()``), dossier réduit aux
4 entrées autorisées, include d'urls + entrée beat + spec e2e retirés, spec
multi-module CONSERVÉE, relance sans effet (idempotence), ``--dry-run`` qui
n'écrit rien, sémantique de ``--check``, refus d'un label non parqué et cassage
d'un cycle de FK mutuelles.
"""
import ast
import importlib
import io
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.apps import apps as registre_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from core.management.commands import parquer_app as cmd

APPS_PY = """from django.apps import AppConfig


class JouetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jouet'
    verbose_name = 'App jouet'
    module_manifest = {'key': 'jouet', 'label': 'Jouet', 'depends': []}

    def ready(self):
        from . import receivers  # noqa: F401
"""

MODELS_PY = """from django.db import models


class Parent(models.Model):
    nom = models.CharField(max_length=20)


class Enfant(models.Model):
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
"""

MIG_0001 = """from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Parent',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('nom', models.CharField(max_length=20)),
            ],
        ),
    ]
"""

MIG_0002 = """import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('jouet', '0001_initial')]
    operations = [
        migrations.CreateModel(
            name='Enfant',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('parent', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='jouet.parent')),
            ],
        ),
    ]
"""

URLS_PY = """from django.urls import include, path


def _si_active(route, module, **kwargs):
    return [path(route, include(module), **kwargs)]


_APP_URLS = [
    path('crm/', include('apps.crm.urls')),
    # Jouet — module de test (ce commentaire part avec l'entree).
    path('jouet/', include('apps.jouet.urls')),
    *_si_active('jouet-bis/', 'apps.jouet.urls_bis'),
    path('stock/', include('apps.stock.urls')),
]

urlpatterns = [
    path('api/django/public/jouet/',
         include('apps.jouet.public_urls')),
    path('api/django/', include(_APP_URLS)),
]
"""

CELERY_PY = """app_conf = object()

beat_schedule = {
    'crm-x': {'task': 'crm.x', 'schedule': 1},
    # Jouet — tache planifiee du module jouet.
    'jouet-nettoyer': {
        'task': 'jouet.nettoyer',
        'schedule': 2,
    },
    'ventes-y': {'task': 'ventes.y', 'schedule': 3},
}
"""


class ParquerAppTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='solmvp2_'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.base = self.tmp / 'backend' / 'django_core'
        (self.base / 'erp_agentique').mkdir(parents=True)
        (self.base / 'erp_agentique' / 'urls.py').write_text(URLS_PY, 'utf-8')
        (self.base / 'erp_agentique' / 'celery.py').write_text(CELERY_PY, 'utf-8')
        for garde in ('crm', 'stock'):
            (self.base / 'apps' / garde).mkdir(parents=True)
        e2e = self.tmp / 'frontend' / 'e2e'
        e2e.mkdir(parents=True)
        (e2e / 'jouet-parcours.spec.js').write_text('// jouet\n', 'utf-8')
        (e2e / 'fumee-ecrans.spec.js').write_text(
            '// balaye apps/jouet ET apps/crm\n', 'utf-8')
        # L'app jouet, dans un paquet importable hors du depot.
        self.paquets = self.tmp / 'paquets'
        self.app_dir = self.paquets / 'jouet'
        (self.app_dir / 'migrations').mkdir(parents=True)
        (self.app_dir / 'tests').mkdir()
        (self.app_dir / 'contract_samples').mkdir()
        fichiers = {
            '__init__.py': '', 'apps.py': APPS_PY, 'models.py': MODELS_PY,
            'views.py': '# vues\n', 'urls.py': '# urls\n',
            'receivers.py': '# receivers\n', 'tasks.py': '# tasks\n',
            'tests/__init__.py': '', 'tests/test_jouet.py': '# test\n',
            'contract_samples/liste.json': '{}\n',
            'migrations/__init__.py': '', 'migrations/0001_initial.py': MIG_0001,
            'migrations/0002_enfant.py': MIG_0002,
        }
        for nom, contenu in fichiers.items():
            (self.app_dir / nom).write_text(contenu, 'utf-8')
        sys.path.insert(0, str(self.paquets))
        self.addCleanup(self._purger_jouet)
        importlib.invalidate_caches()
        self.overrides = self.settings(BASE_DIR=self.base,
                                       INSTALLED_APPS=['jouet'])
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        patch = mock.patch.multiple(cmd.parked,
                                    APPS_PARQUEES=('jouet',),
                                    APPS_PARQUEES_SET=frozenset({'jouet'}))
        patch.start()
        self.addCleanup(patch.stop)

    def _purger_jouet(self):
        """Sans ce nettoyage, le 2e test reimporterait le paquet du 1er."""
        if str(self.paquets) in sys.path:
            sys.path.remove(str(self.paquets))
        for nom in [m for m in list(sys.modules)
                    if m == 'jouet' or m.startswith('jouet.')]:
            del sys.modules[nom]
        registre_apps.all_models.pop('jouet', None)
        importlib.invalidate_caches()

    # -- aides -------------------------------------------------------------
    def _appeler(self, *args):
        """``call_command`` sur une INSTANCE : la découverte des commandes passe
        par INSTALLED_APPS, que ce test réduit volontairement à l'app jouet
        (registre minimal = graphe de migrations minimal, et surtout AUCUN
        ``ready()`` d'app réelle rejoué)."""
        self.sortie = io.StringIO()
        call_command(cmd.Command(), *args, verbosity=0, skip_checks=True,
                     stdout=self.sortie)
        return self.sortie.getvalue()

    def _coquiller(self, *args):
        return self._appeler('jouet', *args)

    @property
    def _migration(self):
        return self.app_dir / 'migrations' / '0003_solmvp_coquille.py'

    def _urls(self):
        return (self.base / 'erp_agentique' / 'urls.py').read_text('utf-8')

    # -- tests -------------------------------------------------------------
    def test_coquille_complete(self):
        self._coquiller()
        source = self._migration.read_text('utf-8')
        compile(source, str(self._migration), 'exec')
        self.assertIn('database_operations=[]', source)
        self.assertIn("('jouet', '0002_enfant')", source)
        self.assertLess(source.index("DeleteModel(name='Enfant')"),
                        source.index("DeleteModel(name='Parent')"),
                        'le modele POINTE doit partir en dernier')
        modeles = self.app_dir / 'models.py'
        corps = ast.parse(modeles.read_text('utf-8')).body
        self.assertEqual(len(corps), 1)
        self.assertIsInstance(corps[0].value, ast.Constant)
        apps_py = (self.app_dir / 'apps.py').read_text('utf-8')
        self.assertIn('parked = True', apps_py)
        self.assertIn("'parked': True", apps_py)
        self.assertNotIn('def ready(', apps_py)
        self.assertIn("name = 'jouet'", apps_py)
        self.assertEqual(
            sorted(p.name for p in self.app_dir.iterdir()
                   if p.name != '__pycache__'),
            ['__init__.py', 'apps.py', 'migrations', 'models.py'])
        urls = self._urls()
        self.assertNotIn('apps.jouet', urls)
        self.assertNotIn('ce commentaire part', urls)
        for garde in ("include('apps.crm.urls')", "include('apps.stock.urls')"):
            self.assertIn(garde, urls)
        beat = (self.base / 'erp_agentique' / 'celery.py').read_text('utf-8')
        self.assertNotIn('jouet', beat)
        self.assertIn("'task': 'crm.x'", beat)
        self.assertIn("'task': 'ventes.y'", beat)
        e2e = self.tmp / 'frontend' / 'e2e'
        self.assertFalse((e2e / 'jouet-parcours.spec.js').exists())
        self.assertTrue((e2e / 'fumee-ecrans.spec.js').exists(),
                        'une spec multi-module ne doit jamais partir')
        self.assertTrue(cmd.est_coquille(self.app_dir))

    def test_makemigrations_check_vert_apres_coquille(self):
        """Le « Done = » de SOLMVP2 : zéro dérive modèle↔migration."""
        self._coquiller()
        # Processus neuf simulé : on oublie le module de modèles déjà importé,
        # sinon le registre garderait en mémoire les classes supprimées.
        self.overrides.disable()
        self._purger_jouet()
        sys.path.insert(0, str(self.paquets))
        importlib.invalidate_caches()
        self.overrides.enable()
        call_command('makemigrations', '--check', '--dry-run', verbosity=0)

    def test_relance_est_un_noop(self):
        self._coquiller()
        empreinte = self._migration.read_text('utf-8')
        avant = sorted(p.name for p in (self.app_dir / 'migrations').iterdir())
        sortie = self._coquiller()
        self.assertIn('DÉJÀ une coquille', sortie)
        self.assertEqual(
            sorted(p.name for p in (self.app_dir / 'migrations').iterdir()),
            avant, 'aucune 2e migration-coquille')
        self.assertEqual(self._migration.read_text('utf-8'), empreinte)

    def test_dry_run_n_ecrit_rien(self):
        urls_avant, listing = self._urls(), sorted(
            p.name for p in self.app_dir.iterdir())
        self._coquiller('--dry-run')
        self.assertFalse(self._migration.exists())
        self.assertEqual(sorted(p.name for p in self.app_dir.iterdir()),
                         listing)
        self.assertEqual(self._urls(), urls_avant)
        self.assertIn('class Parent', (self.app_dir / 'models.py').read_text('utf-8'))

    def test_check_avant_et_apres(self):
        with self.assertRaises(CommandError):
            self._appeler('jouet', '--check')
        with self.assertRaises(CommandError):
            self._appeler('--check')
        self._coquiller()
        self._appeler('jouet', '--check')
        self._appeler('--check')

    def test_label_non_parque_refuse(self):
        with self.assertRaises(CommandError) as ctx:
            self._appeler('crm')
        self.assertIn('APPS_PARQUEES', str(ctx.exception))


class OrdreSuppressionsTests(SimpleTestCase):
    def test_dependants_avant_leurs_cibles(self):
        ordre, cycles = cmd.ordonner_suppressions({
            'Parent': {}, 'Enfant': {'parent': 'Parent'},
            'PetitEnfant': {'enfant': 'Enfant'},
        })
        self.assertEqual(ordre, ['PetitEnfant', 'Enfant', 'Parent'])
        self.assertEqual(cycles, [])

    def test_cycle_casse_par_removefield(self):
        ordre, cycles = cmd.ordonner_suppressions({
            'A': {'vers_b': 'B'}, 'B': {'vers_a': 'A'},
        })
        # Le lien coupe est SORTANT : B devient supprimable, A part apres.
        self.assertEqual(cycles, [('A', 'vers_b')])
        self.assertEqual(ordre, ['B', 'A'])
