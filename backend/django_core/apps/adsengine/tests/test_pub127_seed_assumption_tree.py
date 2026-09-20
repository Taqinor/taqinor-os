"""PUB127 — Tests de la commande de semis de l'arbre + du YAML solaire v1.

``seeding.py`` (import validé, idempotent, ASG5) n'avait AUCUNE commande :
``AssumptionNode`` restait à 0 pour toujours et la porte préflight « arbre semé »
ne pouvait jamais passer au vert. Prouve :

  * ``--file`` est obligatoire (on ne sème jamais un arbre implicite) ;
  * un YAML invalide est REFUSÉ avec TOUTES ses raisons FR, et RIEN n'est écrit ;
  * ``--dry-run`` imprime le plan de semis et n'écrit RIEN ;
  * l'import est IDEMPOTENT : double import = même état (mêmes lignes, mêmes
    identifiants) et le posterior APPRIS n'est jamais rembobiné ;
  * ``--company`` restreint à une société ; sans lui, toutes les actives ;
  * le brouillon COMMITÉ ``docs/engine/solar-tree-seed.yml`` est valide, passe le
    préflight de l'arbre, et son double import laisse le même état.
"""
import io
import os
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import seeding
from apps.adsengine.models import AssumptionNode

# Le YAML solaire vit dans le dépôt (lisible et validé par le fondateur AVANT
# tout import en prod) — on le teste tel qu'il est COMMITÉ, jamais une copie.
SOLAR_SEED = (Path(__file__).resolve().parents[5]
              / 'docs' / 'engine' / 'solar-tree-seed.yml')

VALID_YAML = """
version: 1
nodes:
  - key: hook_facture
    classe: creatif
    enonce_fr: "Le hook « facture » convertit mieux que « économies »."
    enjeux_s: 0.7
    pertinence_r: 0.8
    prior:
      alpha0: 3
      beta0: 2
  - key: angle_autonomie
    classe: angle
    enonce_fr: "L'angle « autonomie » porte mieux que l'angle « écologie »."
    enjeux_s: 0.5
    pertinence_r: 0.6
    invalidation_links: [hook_facture]
"""

INVALID_YAML = """
version: 2
nodes:
  - key: sans_classe
    classe: inconnue
    enonce_fr: ""
    enjeux_s: 5
    pertinence_r: -1
    parent: fantome
"""


def write(tmp, name, content):
    path = os.path.join(tmp, name)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(content)
    return path


class SeedCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Seed Co', slug='pub127-seed', actif=True)

    def _run(self, *args, **kwargs):
        out = io.StringIO()
        call_command('seed_assumption_tree', *args, stdout=out, stderr=out,
                     **kwargs)
        return out.getvalue()

    def test_file_argument_is_required(self):
        with self.assertRaises(CommandError):
            call_command('seed_assumption_tree', stdout=io.StringIO())

    def test_unreadable_file_is_refused(self):
        with self.assertRaises(CommandError) as ctx:
            self._run('--file', 'chemin/qui/nexiste/pas.yml')
        self.assertIn('illisible', str(ctx.exception))
        self.assertEqual(AssumptionNode.objects.count(), 0)

    def test_invalid_yaml_lists_every_french_reason_and_writes_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, 'mauvais.yml', INVALID_YAML)
            out = io.StringIO()
            with self.assertRaises(CommandError):
                call_command('seed_assumption_tree', '--file', path,
                             stdout=out, stderr=out)
        text = out.getvalue()
        self.assertIn('REFUSÉ', text)
        self.assertIn('Version de semis inattendue', text)
        self.assertIn('classe', text)
        self.assertEqual(AssumptionNode.objects.count(), 0)

    def test_dry_run_prints_the_plan_and_writes_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, 'bon.yml', VALID_YAML)
            text = self._run('--file', path, '--dry-run')
        self.assertIn('Plan de semis — 2 nœud(s)', text)
        self.assertIn('hook_facture', text)
        self.assertIn('prior Beta(3, 2)', text)
        self.assertIn('AUCUNE écriture', text)
        self.assertEqual(AssumptionNode.objects.count(), 0)

    def test_import_creates_the_nodes_and_their_links(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, 'bon.yml', VALID_YAML)
            text = self._run('--file', path)
        self.assertIn('2 nœud(s) créé(s)', text)
        self.assertEqual(
            AssumptionNode.objects.filter(company=self.company).count(), 2)
        angle = AssumptionNode.objects.get(
            company=self.company, classe=AssumptionNode.Classe.ANGLE)
        self.assertEqual(
            [n.classe for n in angle.invalidation_links.all()],
            [AssumptionNode.Classe.CREATIF])
        hook = AssumptionNode.objects.get(
            company=self.company, classe=AssumptionNode.Classe.CREATIF)
        # Le posterior DÉMARRE au prior (démarrage à froid §3.4).
        self.assertEqual((hook.alpha, hook.beta), (3.0, 2.0))

    def test_double_import_is_idempotent_and_never_rewinds_learning(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, 'bon.yml', VALID_YAML)
            self._run('--file', path)
            hook = AssumptionNode.objects.get(
                company=self.company, classe=AssumptionNode.Classe.CREATIF)
            # Le moteur a appris depuis le semis.
            hook.alpha, hook.beta = 11.0, 4.0
            hook.statut = AssumptionNode.Statut.VALIDATED
            hook.save(update_fields=['alpha', 'beta', 'statut'])
            pks_before = set(
                AssumptionNode.objects.values_list('pk', flat=True))

            text = self._run('--file', path)

        self.assertIn('0 nœud(s) créé(s)', text)
        self.assertIn('2 mis à jour', text)
        self.assertEqual(
            set(AssumptionNode.objects.values_list('pk', flat=True)),
            pks_before)
        hook.refresh_from_db()
        self.assertEqual((hook.alpha, hook.beta), (11.0, 4.0))
        self.assertEqual(hook.statut, AssumptionNode.Statut.VALIDATED)

    def test_company_option_restricts_the_seed(self):
        other = Company.objects.create(
            nom='Autre', slug='pub127-autre', actif=True)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, 'bon.yml', VALID_YAML)
            self._run('--file', path, '--company', 'pub127-seed')
        self.assertEqual(
            AssumptionNode.objects.filter(company=self.company).count(), 2)
        self.assertEqual(
            AssumptionNode.objects.filter(company=other).count(), 0)

    def test_unknown_company_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, 'bon.yml', VALID_YAML)
            with self.assertRaises(CommandError):
                self._run('--file', path, '--company', 'nexiste-pas')
        self.assertEqual(AssumptionNode.objects.count(), 0)


class SolarSeedFileTests(TestCase):
    """Le brouillon COMMITÉ est réellement importable (pas un YAML de papier)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Solar Co', slug='pub127-solar', actif=True)

    def _text(self):
        self.assertTrue(SOLAR_SEED.exists(), f'{SOLAR_SEED} absent du dépôt')
        return SOLAR_SEED.read_text(encoding='utf-8')

    def test_committed_yaml_validates(self):
        data = seeding.validate(self._text())
        self.assertEqual(data['version'], seeding.SEED_VERSION)
        self.assertGreaterEqual(len(data['nodes']), 2)

    def test_every_prior_is_declared_assumed(self):
        # Checked-facts : un prior de jour 0 est une SUPPOSITION, jamais une
        # mesure — chaque nœud le dit explicitement.
        data = seeding.validate(self._text())
        statuts = {n.get('statut', 'assumed') for n in data['nodes']}
        self.assertEqual(statuts, {AssumptionNode.Statut.ASSUMED.value})

    def test_double_import_of_the_committed_file_is_idempotent(self):
        text = self._text()
        first = seeding.import_seed(self.company, text)
        count_after_first = AssumptionNode.objects.filter(
            company=self.company).count()
        second = seeding.import_seed(self.company, text)
        self.assertEqual(first['created'], count_after_first)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['updated'], count_after_first)
        self.assertEqual(
            AssumptionNode.objects.filter(company=self.company).count(),
            count_after_first)

    def test_seeded_tree_passes_the_preflight(self):
        seeding.import_seed(self.company, self._text())
        status = seeding.preflight(self.company)
        self.assertTrue(status['ready'], status['missing_fr'])
        self.assertEqual(status['missing_fr'], [])

    def test_command_seeds_the_committed_file(self):
        out = io.StringIO()
        call_command('seed_assumption_tree', '--file', str(SOLAR_SEED),
                     '--company', 'pub127-solar', stdout=out, stderr=out)
        self.assertGreater(
            AssumptionNode.objects.filter(company=self.company).count(), 1)
        self.assertIn('seed_assumption_tree', out.getvalue())
