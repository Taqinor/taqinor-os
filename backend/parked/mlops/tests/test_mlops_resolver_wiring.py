"""MLOPS-RESOLVER — ``apps.mlops.apps.MlopsConfig.ready()`` branche
``selectors.params_actifs`` comme résolveur d'hyperparamètres de
``core.score_params`` (NTAI27), sans que ``core`` importe jamais
``apps.mlops`` (contrat import-linter core-foundation-is-a-base-layer).

``ready()`` est rappelé explicitement (idempotent) plutôt que de compter sur
l'ordre d'exécution avec ``core/tests/test_ntai27_score_params.py`` — ce
dernier nettoie le résolveur global dans son propre ``tearDown``."""
from django.apps import apps as django_apps
from django.test import TestCase

from apps.mlops.models import ModeleML
from apps.mlops.selectors import params_actifs
from authentication.models import Company
from core import score_params


class ResolverWiringTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            slug='mlops-resolver-wiring', nom='MLOps Resolver Wiring')
        django_apps.get_app_config('mlops').ready()

    def tearDown(self):
        score_params.clear_params_resolver()
        super().tearDown()

    def test_ready_enregistre_selectors_params_actifs(self):
        self.assertIs(
            score_params.registered_params_resolver(), params_actifs)

    def test_core_score_params_lit_via_le_resolveur_mlops(self):
        ModeleML.objects.create(
            company=self.company, nom=score_params.NOM_CHURN, version=1,
            params_json={'seuil': 0.42}, actif=True)
        self.assertEqual(
            score_params.params_actifs(self.company, score_params.NOM_CHURN),
            {'seuil': 0.42})

    def test_sans_version_active_core_recoit_un_mapping_vide(self):
        # Contrat NTAI27 : `params_actifs` (core) rend {} sans version
        # active — c'est `resoudre()`/les scorers qui appliquent les défauts.
        self.assertEqual(
            score_params.params_actifs(self.company, score_params.NOM_CHURN),
            {})
