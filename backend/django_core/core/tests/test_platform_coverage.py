"""ARC41 — garde de couverture des SURFACES plateforme (matrice de dérive).

Complète YEVNT7 (``test_event_coverage`` garde le BUS) : ici on garde la
cohérence INTER-MANIFESTES ARC28 — un modèle chatter-isé mais introuvable en
recherche, cherchable mais sans chatter, etc. Politique « rouge sur RÉGRESSION » :
seule une incohérence NOUVELLE (hors ``BASELINE_DRIFT``) casse le build ; les
dérives connues sont listées en warnings dans la matrice.

Le test IMPRIME la matrice de dérive (comme la couverture d'event_coverage
remonte ses ensembles) et vérifie que l'infra YEVNT7 reste intacte (aucune
duplication : ce module ne recense NI signaux NI EventType).
"""
from django.test import SimpleTestCase

from core import platform, platform_coverage


class PlatformCoverageTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifests = platform.collect_platform_manifests()

    def test_no_new_surface_drift(self):
        """Aucune incohérence de surface NOUVELLE au-delà de la baseline."""
        nouvelles = platform_coverage.new_drift(self.manifests)
        # La matrice complète est jointe pour rendre la régression lisible.
        self.assertEqual(
            nouvelles, set(),
            "Nouvelles incohérences inter-surfaces (au-delà de "
            "BASELINE_DRIFT) :\n"
            + '\n'.join(f'  - {m} : {c}' for (m, c) in sorted(nouvelles))
            + "\n\nMatrice de dérive complète :\n"
            + platform_coverage.format_matrix(self.manifests)
            + "\n\nCâblez la surface manquante, ou (dérive assumée) ajoutez "
            "l'entrée à core.platform_coverage.BASELINE_DRIFT avec une "
            "justification.")

    def test_baseline_stays_minimal(self):
        """Une entrée baseline qui n'est plus une incohérence doit être retirée."""
        stale = platform_coverage.stale_baseline(self.manifests)
        self.assertEqual(
            stale, set(),
            "BASELINE_DRIFT liste des incohérences qui n'existent plus "
            "(surface enfin câblée) — retirez-les : "
            f"{sorted(stale)}")

    def test_known_contrat_drift_is_detected(self):
        """ARC29 — le trou historique est comblé : Contrat est désormais
        chatter-isé ET cherchable, donc plus AUCUNE dérive ne le concerne.
        Preuve que le croisement marche encore : on simule un manifeste
        chatter-sans-recherche pour vérifier que la règle est toujours active."""
        drift = platform_coverage.all_drift(self.manifests)
        self.assertNotIn(('contrats.contrat', 'chatter_sans_recherche'), drift)
        faux = dict(self.manifests)
        faux['bidon_chatter'] = {
            'module': 'bidon_chatter',
            'searchable_models': [],
            'record_targets': ['bidon.truc'],
            'customfield_models': [], 'import_specs': [],
            'agent_actions_module': '', 'automation_state_fields': [],
            'kpi_providers': [],
        }
        self.assertIn(
            ('bidon.truc', 'chatter_sans_recherche'),
            platform_coverage.all_drift(faux))

    def test_matrix_lists_pilot_models(self):
        """La matrice remonte bien des modèles réels (crm + contrats)."""
        rows = {r['model']: r for r in
                platform_coverage.platform_matrix(self.manifests)}
        self.assertIn('crm.lead', rows)
        self.assertIn('contrats.contrat', rows)
        # crm.lead : cherchable ET chatter-isé ET automatisable (aucune dérive).
        self.assertTrue(rows['crm.lead']['searchable'])
        self.assertTrue(rows['crm.lead']['record_target'])
        self.assertTrue(rows['crm.lead']['automation'])
        self.assertEqual(rows['crm.lead']['drift'], [])
        # ARC29 — contrats.contrat : chatter-isé ET cherchable → plus de dérive.
        self.assertTrue(rows['contrats.contrat']['record_target'])
        self.assertTrue(rows['contrats.contrat']['searchable'])
        self.assertEqual(rows['contrats.contrat']['drift'], [])

    def test_matrix_renders_without_error(self):
        """La sortie texte de la matrice est produite (elle apparaît en régression)."""
        rendu = platform_coverage.format_matrix(self.manifests)
        self.assertIn('crm.lead', rendu)
        self.assertIn('contrats.contrat', rendu)

    def test_regression_would_be_red(self):
        """Simule une NOUVELLE dérive (manifeste fictif) → détectée hors baseline."""
        faux = dict(self.manifests)
        faux['bidon'] = {
            'module': 'bidon',
            # cherchable mais SANS chatter → règle 'recherche_sans_chatter'.
            'searchable_models': ['bidon.machin'],
            'record_targets': [],
            'customfield_models': [],
            'import_specs': [],
            'agent_actions_module': '',
            'automation_state_fields': [],
            'kpi_providers': [],
        }
        nouvelles = platform_coverage.new_drift(faux)
        self.assertIn(('bidon.machin', 'recherche_sans_chatter'), nouvelles)

    def test_does_not_duplicate_event_coverage_infra(self):
        """YEVNT7 intact : ARC41 ne recense NI signaux NI EventType (zéro doublon)."""
        # Le module de couverture des surfaces n'expose aucune API du bus.
        for attr in ('declared_signals', 'orphan_signals',
                     'unproduced_eventtypes', 'eventtype_coverage'):
            self.assertFalse(
                hasattr(platform_coverage, attr),
                f"platform_coverage ne doit pas dupliquer event_coverage.{attr}")
