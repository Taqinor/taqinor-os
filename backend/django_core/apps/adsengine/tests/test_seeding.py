"""ASG5 — Tests du format de semis YAML + validateur (dd-assumption-engine §4).

Prouve :
  * un semis invalide est REFUSÉ avec des raisons FR (toutes d'un coup) ;
  * un semis valide s'importe (nœuds + parent + invalidation_links) ;
  * double import = MÊME état (idempotent, aucun doublon, posterior préservé) ;
  * le préflight (arbre ≥N testables, backlog créatif compatible) tranche.
"""
import textwrap

from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import seeding
from apps.adsengine.models import AssumptionNode

VALID_SEED = textwrap.dedent("""
    version: 1
    nodes:
      - key: hook_facture
        classe: creatif
        enonce_fr: "Le hook facture convertit mieux."
        enjeux_s: 0.7
        pertinence_r: 0.8
        tags_saison: [ramadan]
        prior: {alpha0: 3, beta0: 2}
        demi_vie_semaines: 8
      - key: hook_video
        classe: creatif
        enonce_fr: "Le hook facture gagne en vidéo."
        enjeux_s: 0.4
        pertinence_r: 0.6
        parent: hook_facture
        invalidation_links: [hook_facture]
      - key: angle_ete
        classe: angle
        enonce_fr: "L'angle facture d'été porte l'été."
        enjeux_s: 0.5
        pertinence_r: 0.5
""")


class SeedValidationTests(SimpleTestCase):
    """Validation pure (aucune base)."""

    def test_valid_seed_passes(self):
        data = seeding.validate(VALID_SEED)
        self.assertEqual(len(data['nodes']), 3)

    def test_bad_version_rejected(self):
        with self.assertRaises(seeding.SeedValidationError) as ctx:
            seeding.validate("version: 2\nnodes: [{key: a, classe: creatif, "
                             "enonce_fr: x, enjeux_s: 0.5, pertinence_r: 0.5}]")
        self.assertTrue(any('Version' in r for r in ctx.exception.reasons_fr))

    def test_empty_nodes_rejected(self):
        with self.assertRaises(seeding.SeedValidationError) as ctx:
            seeding.validate("version: 1\nnodes: []")
        self.assertTrue(ctx.exception.reasons_fr)

    def test_collects_multiple_reasons_at_once(self):
        bad = textwrap.dedent("""
            version: 1
            nodes:
              - key: a
                classe: pas_une_classe
                enonce_fr: ""
                enjeux_s: 5
                pertinence_r: -1
        """)
        with self.assertRaises(seeding.SeedValidationError) as ctx:
            seeding.validate(bad)
        reasons = ctx.exception.reasons_fr
        # classe illégale + énoncé vide + S hors bornes + R hors bornes.
        self.assertGreaterEqual(len(reasons), 4)

    def test_duplicate_key_rejected(self):
        bad = textwrap.dedent("""
            version: 1
            nodes:
              - key: a
                classe: creatif
                enonce_fr: X
                enjeux_s: 0.5
                pertinence_r: 0.5
              - key: a
                classe: angle
                enonce_fr: Y
                enjeux_s: 0.5
                pertinence_r: 0.5
        """)
        with self.assertRaises(seeding.SeedValidationError) as ctx:
            seeding.validate(bad)
        self.assertTrue(
            any('dupliqu' in r for r in ctx.exception.reasons_fr))

    def test_dangling_parent_rejected(self):
        bad = textwrap.dedent("""
            version: 1
            nodes:
              - key: a
                classe: creatif
                enonce_fr: X
                enjeux_s: 0.5
                pertinence_r: 0.5
                parent: inconnu
        """)
        with self.assertRaises(seeding.SeedValidationError) as ctx:
            seeding.validate(bad)
        self.assertTrue(
            any('introuvable' in r for r in ctx.exception.reasons_fr))

    def test_dangling_invalidation_link_rejected(self):
        bad = textwrap.dedent("""
            version: 1
            nodes:
              - key: a
                classe: creatif
                enonce_fr: X
                enjeux_s: 0.5
                pertinence_r: 0.5
                invalidation_links: [ghost]
        """)
        with self.assertRaises(seeding.SeedValidationError):
            seeding.validate(bad)

    def test_self_parent_rejected(self):
        bad = textwrap.dedent("""
            version: 1
            nodes:
              - key: a
                classe: creatif
                enonce_fr: X
                enjeux_s: 0.5
                pertinence_r: 0.5
                parent: a
        """)
        with self.assertRaises(seeding.SeedValidationError):
            seeding.validate(bad)


class SeedImportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASG Seed', slug='asg-seed')

    def test_import_creates_nodes_and_relations(self):
        result = seeding.import_seed(self.company, VALID_SEED)

        self.assertEqual(result['created'], 3)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(
            AssumptionNode.objects.filter(company=self.company).count(), 3)

        video = AssumptionNode.objects.get(
            company=self.company, enonce_fr="Le hook facture gagne en vidéo.")
        facture = AssumptionNode.objects.get(
            company=self.company, enonce_fr="Le hook facture convertit mieux.")
        self.assertEqual(video.parent_id, facture.pk)
        self.assertEqual(
            list(video.invalidation_links.values_list('pk', flat=True)),
            [facture.pk])

    def test_prior_sets_posterior_on_create(self):
        seeding.import_seed(self.company, VALID_SEED)
        facture = AssumptionNode.objects.get(
            company=self.company, enonce_fr="Le hook facture convertit mieux.")
        # Démarrage à froid : posterior démarre AU prior (§3.4).
        self.assertEqual((facture.alpha0, facture.beta0), (3.0, 2.0))
        self.assertEqual((facture.alpha, facture.beta), (3.0, 2.0))

    def test_double_import_same_state(self):
        seeding.import_seed(self.company, VALID_SEED)
        result2 = seeding.import_seed(self.company, VALID_SEED)

        self.assertEqual(result2['created'], 0)   # aucun doublon
        self.assertEqual(result2['updated'], 3)
        self.assertEqual(
            AssumptionNode.objects.filter(company=self.company).count(), 3)

    def test_reimport_preserves_learned_posterior(self):
        seeding.import_seed(self.company, VALID_SEED)
        facture = AssumptionNode.objects.get(
            company=self.company, enonce_fr="Le hook facture convertit mieux.")
        # Simule un apprentissage puis un changement de statut.
        facture.alpha, facture.beta = 40.0, 8.0
        facture.statut = AssumptionNode.Statut.VALIDATED
        facture.save()

        seeding.import_seed(self.company, VALID_SEED)

        facture.refresh_from_db()
        # Réimport : posterior appris ET statut PRÉSERVÉS.
        self.assertEqual((facture.alpha, facture.beta), (40.0, 8.0))
        self.assertEqual(facture.statut, AssumptionNode.Statut.VALIDATED)

    def test_import_is_company_scoped(self):
        other = Company.objects.create(nom='Autre', slug='autre-seed')
        seeding.import_seed(self.company, VALID_SEED)
        self.assertEqual(
            AssumptionNode.objects.filter(company=other).count(), 0)


class SeedPreflightTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASG PF', slug='asg-pf')

    def _node(self, **kw):
        defaults = dict(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='n', enjeux_s=0.5, pertinence_r=0.5)
        defaults.update(kw)
        return AssumptionNode.objects.create(**defaults)

    def test_empty_tree_not_ready(self):
        pf = seeding.preflight(self.company)
        self.assertFalse(pf['ready'])
        self.assertTrue(pf['missing_fr'])

    def test_seeded_tree_ready(self):
        seeding.import_seed(self.company, VALID_SEED)
        pf = seeding.preflight(self.company)
        self.assertTrue(pf['ready'], pf['missing_fr'])

    def test_no_creatif_fails_backlog_compat(self):
        # Deux nœuds testables mais aucun créatif → backlog incompatible.
        self._node(classe=AssumptionNode.Classe.ANGLE, enonce_fr='a1')
        self._node(
            classe=AssumptionNode.Classe.AUDIENCE_STRUCTURE, enonce_fr='a2')
        pf = seeding.preflight(self.company)
        self.assertFalse(pf['ready'])
        self.assertTrue(any('créatif' in m for m in pf['missing_fr']))

    def test_retired_and_zero_sr_not_testable(self):
        self._node(enonce_fr='ok1')
        self._node(enonce_fr='ok2')
        self._node(enonce_fr='ret', statut=AssumptionNode.Statut.RETIRED)
        self._node(enonce_fr='zero', enjeux_s=0.0)
        pf = seeding.preflight(self.company)
        # 2 testables (ok1, ok2) → ready.
        self.assertTrue(pf['ready'], pf['missing_fr'])
