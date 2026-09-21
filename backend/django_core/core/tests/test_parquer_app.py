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

Couvert aussi (contrat du TALON) : une app jouet dont la migration référence
``apps.jouet.models._jeton_defaut`` garde ce symbole — et les imports/constantes
dont il dépend — dans son ``models.py`` de coquille ; un symbole introuvable ou
qui est un MODÈLE fait REFUSER la commande ; et la vérification à froid du
graphe, quand elle échoue, REMET models.py/apps.py et la migration-coquille en
l'état. La vérification à froid elle-même est neutralisée dans ces tests (elle
lancerait un sous-processus Django sur le dépôt RÉEL, pas sur l'app jouet).
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
        # La vérification à froid lancerait un sous-processus Django sur le
        # DÉPÔT réel (cwd=BASE_DIR temporaire, settings introuvables) : hors
        # sujet ici. Sa sémantique est testée par TalonModelsPyTests.
        froid = mock.patch.object(cmd, 'verifier_graphe_en_sous_processus',
                                  return_value='')
        froid.start()
        self.addCleanup(froid.stop)

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


TALON_MODELS_PY = """import secrets

from django.db import models

JETON_OCTETS = 24


def _jeton_defaut():
    \"\"\"Jeton public imprevisible (reference par la migration 0001).\"\"\"
    return secrets.token_urlsafe(JETON_OCTETS)


def jamais_reference():
    return 'ce symbole ne doit PAS finir dans le talon'


class Chose(models.Model):
    jeton = models.CharField(max_length=64, default=_jeton_defaut)
"""

TALON_MIG_0001 = """import talon.models
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Chose',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('jeton', models.CharField(
                    default=talon.models._jeton_defaut, max_length=64)),
            ],
        ),
    ]
"""


class TalonModelsPyTests(SimpleTestCase):
    """Contrat du TALON : une migration GELÉE qui référence un symbole de
    ``models.py`` fait garder ce symbole (et ses dépendances) dans la coquille.

    Sans cela, ``models.py`` vidé rend la migration inimportable et le graphe
    ENTIER casse — panne qui n'apparaît QUE dans un processus neuf, d'où la
    vérification à froid vérifiée ici aussi (appel + restauration en cas
    d'échec).
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='solmvp2_talon_'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.base = self.tmp / 'backend' / 'django_core'
        self.base.mkdir(parents=True)
        self.paquets = self.tmp / 'paquets'
        self.app_dir = self.paquets / 'talon'
        (self.app_dir / 'migrations').mkdir(parents=True)
        for nom, contenu in {
            '__init__.py': '', 'apps.py': APPS_PY.replace('jouet', 'talon'),
            'models.py': TALON_MODELS_PY, 'views.py': '# vues\n',
            'receivers.py': '# receivers\n',
            'migrations/__init__.py': '',
            'migrations/0001_initial.py': TALON_MIG_0001,
        }.items():
            (self.app_dir / nom).write_text(contenu, 'utf-8')
        sys.path.insert(0, str(self.paquets))
        self.addCleanup(self._purger)
        importlib.invalidate_caches()
        self.overrides = self.settings(BASE_DIR=self.base,
                                       INSTALLED_APPS=['talon'])
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        patch = mock.patch.multiple(cmd.parked,
                                    APPS_PARQUEES=('talon',),
                                    APPS_PARQUEES_SET=frozenset({'talon'}))
        patch.start()
        self.addCleanup(patch.stop)

    def _purger(self):
        if str(self.paquets) in sys.path:
            sys.path.remove(str(self.paquets))
        for nom in [m for m in list(sys.modules)
                    if m == 'talon' or m.startswith('talon.')]:
            del sys.modules[nom]
        registre_apps.all_models.pop('talon', None)
        importlib.invalidate_caches()

    def _coquiller(self, *args, **kwargs):
        sortie = io.StringIO()
        call_command(cmd.Command(), 'talon', *args, verbosity=0,
                     skip_checks=True, stdout=sortie, **kwargs)
        return sortie.getvalue()

    def _models_py(self):
        return (self.app_dir / 'models.py').read_text('utf-8')

    # -- tests -------------------------------------------------------------
    def test_symboles_reclames_lus_dans_les_migrations(self):
        self.assertEqual(
            sorted(cmd.symboles_reclames(self.app_dir, 'talon')),
            ['_jeton_defaut'])

    def test_talon_garde_le_symbole_et_ses_dependances(self):
        with mock.patch.object(cmd, 'verifier_graphe_en_sous_processus',
                               return_value='') as froid:
            self._coquiller()
        self.assertEqual(froid.call_count, 1,
                         'le graphe doit être vérifié à FROID avant suppression')
        source = self._models_py()
        compile(source, 'models.py', 'exec')
        self.assertIn('def _jeton_defaut():', source)
        self.assertIn('import secrets', source)
        self.assertIn('JETON_OCTETS = 24', source)
        self.assertNotIn('jamais_reference', source)
        self.assertNotIn('class Chose', source)
        # Contrat de coquille : aucun modèle Django, et l'app est une coquille.
        self.assertEqual(cmd.parked.modeles_declares(source), [])
        self.assertTrue(cmd.est_coquille(self.app_dir))
        self.assertEqual(
            sorted(p.name for p in self.app_dir.iterdir()
                   if p.name != '__pycache__'),
            ['__init__.py', 'apps.py', 'migrations', 'models.py'])

    def test_echec_a_froid_remet_tout_en_etat(self):
        avant = (self._models_py(),
                 (self.app_dir / 'apps.py').read_text('utf-8'))
        with mock.patch.object(cmd, 'verifier_graphe_en_sous_processus',
                               return_value='AttributeError: _jeton_defaut'):
            with self.assertRaises(CommandError) as ctx:
                self._coquiller()
        self.assertIn('ne charge PLUS', str(ctx.exception))
        self.assertEqual((self._models_py(),
                          (self.app_dir / 'apps.py').read_text('utf-8')), avant)
        self.assertFalse(
            (self.app_dir / 'migrations' / '0002_solmvp_coquille.py').exists(),
            'la migration-coquille doit être retirée quand le graphe casse')
        self.assertTrue((self.app_dir / 'views.py').is_file(),
                        'aucun fichier ne doit partir avant la vérif à froid')

    def test_symbole_introuvable_ou_modele_refuse(self):
        mig = self.app_dir / 'migrations' / '0001_initial.py'
        mig.write_text(TALON_MIG_0001.replace('_jeton_defaut', 'Chose'), 'utf-8')
        with self.assertRaises(CommandError) as ctx:
            self._coquiller('--dry-run')
        self.assertIn('Chose', str(ctx.exception))
        self.assertIn('classe-namespace', str(ctx.exception))
        mig.write_text(TALON_MIG_0001.replace('_jeton_defaut', '_disparu'),
                       'utf-8')
        with self.assertRaises(CommandError) as ctx:
            self._coquiller('--dry-run')
        self.assertIn('_disparu', str(ctx.exception))
        self.assertIn('introuvables', str(ctx.exception))


class ExtraireTalonTests(SimpleTestCase):
    SOURCE = (
        'import secrets\n'
        'from django.db import models\n'
        'TAILLE = 32\n'
        'AUTRE = 1\n'
        '\n'
        'def jeton():\n'
        '    return secrets.token_urlsafe(TAILLE)\n'
        '\n'
        'class Sens(models.TextChoices):\n'
        "    DEBIT = 'debit', 'Débit'\n"
        '\n'
        'class Ecriture(models.Model):\n'
        '    pass\n'
    )

    def test_fermeture_des_dependances(self):
        code, manquants, bloquants = cmd.extraire_talon(self.SOURCE, ['jeton'])
        self.assertEqual((manquants, bloquants), ([], []))
        self.assertIn('import secrets', code)
        self.assertIn('TAILLE = 32', code)
        self.assertNotIn('AUTRE', code)
        self.assertNotIn('Sens', code)

    def test_enumeration_extraite_avec_son_import(self):
        code, manquants, bloquants = cmd.extraire_talon(self.SOURCE, ['Sens'])
        self.assertEqual((manquants, bloquants), ([], []))
        self.assertIn('from django.db import models', code)
        self.assertIn('class Sens(models.TextChoices):', code)

    def test_modele_et_absent_signales(self):
        _, manquants, bloquants = cmd.extraire_talon(
            self.SOURCE, ['Ecriture', 'fantome'])
        self.assertEqual(manquants, ['fantome'])
        self.assertEqual(bloquants, ['Ecriture'])


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
