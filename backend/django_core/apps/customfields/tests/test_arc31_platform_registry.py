"""ARC31 — cibles customfields peuplées depuis le registre plateforme
(core.platform) au lieu d'un ``AppConfig.ready()`` par app pilote.

Couvre : (1) non-régression stricte — les clés natives GARDÉES résolvent
EXACTEMENT comme avant ARC31 ; (2) une nouvelle cible déclarée SEULEMENT via
un manifeste fictif (jamais via apps/customfields) devient enregistrée.

SOLMVP20 — la clé native ``employe`` (app PARQUÉE RH) et les pilotes
historiques ``contrat``/``vehicule`` (apps PARQUÉES, Groupe SOLMVP) ont été
retirés de cette couverture ; la preuve du chargeur central reste faite par
le manifeste FICTIF ci-dessous, indépendant de toute app réelle.
``document`` (GED) reste couverte : la GED est dans le MVP solaire
(SOLMVP16b).
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.customfields import registry


class TestNativeModulesNonRegression(SimpleTestCase):
    """Les clés natives GARDÉES résolvent identiquement à avant ARC31."""

    def test_native_keys_still_registered(self):
        for key in ('lead', 'client', 'produit', 'devis', 'installation',
                    'ticket', 'document', 'fournisseur'):
            self.assertTrue(registry.is_registered(key), key)

    def test_native_keys_resolve_to_expected_models(self):
        from apps.crm.models import Client, Lead
        from apps.ged.models import Document
        from apps.installations.models import Installation
        from apps.sav.models import Ticket
        from apps.stock.models import Fournisseur, Produit
        from apps.ventes.models import Devis

        expected = {
            'lead': Lead, 'client': Client, 'produit': Produit,
            'devis': Devis, 'installation': Installation, 'ticket': Ticket,
            'document': Document, 'fournisseur': Fournisseur,
        }
        for key, model in expected.items():
            self.assertIs(registry.get_model(key), model, key)


class TestNewManifestTargetRegistersWithoutTouchingCustomfields(SimpleTestCase):
    """Une cible customfieldable déclarée UNIQUEMENT dans un manifeste fictif
    (jamais en modifiant apps/customfields) devient enregistrée par le
    chargeur central."""

    def test_fictitious_manifest_customfield_model_is_registered(self):
        from core import platform as core_platform

        vrais = core_platform.collect_platform_manifests()
        faux = dict(vrais)
        faux['bidon_arc31'] = {
            'module': 'bidon_arc31',
            'customfield_models': ['zorglub_arc31'],
            'record_targets': [], 'searchable_models': [],
            'import_specs': [], 'agent_actions_module': '',
            'automation_state_fields': [], 'kpi_providers': [],
        }

        def _fake_collect():
            return faux

        try:
            with mock.patch(
                    'core.platform.collect_platform_manifests',
                    side_effect=_fake_collect):
                registry.register_from_platform_manifests()
            self.assertTrue(registry.is_registered('zorglub_arc31'))
        finally:
            registry.unregister('zorglub_arc31')
