"""SOL15 — les baselines qui épinglent le SET COMPLET d'apps survivent à l'édition.

`BASELINE_DRIFT` est une liste d'`app.model`. En édition solaire, les sept apps
parquées ne sont pas chargées : leurs entrées ne peuvent plus apparaître dans
`all_drift()` et deviendraient donc « périmées » d'un coup — la garde rougirait
pour une raison FAUSSE (l'entrée n'est pas obsolète, elle est hors périmètre),
et la seule façon de la faire taire aurait été de supprimer une entrée qui
redevient vraie dès qu'on recharge l'édition complète.
"""
from django.test import TestCase

from core import platform_coverage
from erp_agentique.settings import editions


class BaselineDriftParEditionTests(TestCase):
    def test_edition_complete_inchangee(self):
        """Comportement byte-identique quand rien n'est parqué."""
        self.assertEqual(platform_coverage._apps_hors_edition(), set())
        self.assertEqual(platform_coverage.stale_baseline(), set())
        self.assertEqual(platform_coverage.new_drift(), set())

    def test_une_entree_d_app_parquee_n_est_pas_perimee(self):
        """La règle SOL15, prouvée sur un faux jeu de manifestes.

        On simule l'édition solaire en filtrant les manifestes : l'entrée
        `mrp.ordrefabrication` de la baseline disparaît alors de `all_drift`,
        et sans la garde elle serait comptée comme périmée.
        """
        manifests = platform_coverage.platform.collect_platform_manifests()
        parquees = editions.modules_parques(editions.EDITION_SOLAR)
        sans_parquees = {
            cle: manifeste for cle, manifeste in manifests.items()
            if cle not in parquees
        }
        perimees_brutes = (
            platform_coverage.BASELINE_DRIFT
            - platform_coverage.all_drift(sans_parquees))
        entrees_parquees = {
            (model, code) for (model, code) in perimees_brutes
            if model.split('.', 1)[0] in parquees
        }
        self.assertTrue(
            entrees_parquees,
            "la baseline ne contient plus AUCUNE entrée d'app parquée — ce "
            'test ne prouve plus rien ; le retirer ou le recalibrer.')

    def test_le_filtre_retire_bien_les_apps_hors_edition(self):
        """Le filtre lui-même, sans dépendre de l'édition courante."""
        perimees = {('mrp.ordrefabrication', 'chatter_sans_recherche'),
                    ('ao.appeloffre', 'chatter_sans_recherche')}
        gardees = {
            (model, code) for (model, code) in perimees
            if model.split('.', 1)[0] not in {'mrp'}
        }
        self.assertEqual(
            gardees, {('ao.appeloffre', 'chatter_sans_recherche')})


class GardeEditionsDansLaCiTests(TestCase):
    """Les gardes d'édition sont bien CÂBLÉES dans la CI (pas seulement écrites)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from pathlib import Path

        from django.conf import settings

        racine = Path(settings.BASE_DIR).resolve().parent.parent
        cls.ci = (racine / '.github' / 'workflows' / 'ci.yml')
        cls.hebdo = (racine / '.github' / 'workflows' / 'editions.yml')

    def test_le_job_solar_boot_existe_et_est_agrege(self):
        if not self.ci.is_file():
            self.skipTest('.github non monté dans cet environnement')
        texte = self.ci.read_text(encoding='utf-8')
        self.assertIn('solar-boot:', texte)
        self.assertIn('- solar-boot', texte)
        self.assertIn('check_dist_edition.mjs', texte)
        self.assertIn('check_editions_decouplage.py', texte)
        self.assertIn('verifier_edition', texte)

    def test_le_passage_hebdomadaire_existe_et_alerte(self):
        if not self.hebdo.is_file():
            self.skipTest('.github non monté dans cet environnement')
        texte = self.hebdo.read_text(encoding='utf-8')
        self.assertIn('migrate --noinput', texte)
        self.assertIn('lint-imports', texte)
        # Un job hebdomadaire qui rougit sans réveiller personne ne sert à rien.
        self.assertIn('alerte-editions', texte)
        self.assertIn('issues: write', texte)
