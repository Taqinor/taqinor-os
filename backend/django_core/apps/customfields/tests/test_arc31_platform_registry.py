"""ARC31 — cibles customfields peuplées depuis le registre plateforme
(core.platform) au lieu d'un ``AppConfig.ready()`` par app pilote.

Couvre : (1) non-régression stricte — les 8 clés natives + les 2 pilotes
historiques (contrat, vehicule) résolvent EXACTEMENT comme avant ARC31 ; (2)
la source de peuplement des pilotes est bien le manifeste ``platform.py``
(``contrats.apps.ContratsConfig.ready()``/``flotte.apps.FlotteConfig`` ne les
enregistrent plus explicitement) ; (3) une nouvelle cible déclarée SEULEMENT
via un manifeste fictif (jamais via apps/customfields) devient enregistrée.
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.customfields import registry


class TestNativeAndPilotNonRegression(SimpleTestCase):
    """Les 8 clés natives + 2 pilotes résolvent identiquement à avant ARC31."""

    def test_eight_native_keys_still_registered(self):
        for key in ('lead', 'client', 'produit', 'devis', 'installation',
                    'ticket', 'document', 'fournisseur', 'employe'):
            self.assertTrue(registry.is_registered(key), key)

    def test_native_keys_resolve_to_expected_models(self):
        from apps.crm.models import Client, Lead
        from apps.ged.models import Document
        from apps.installations.models import Installation
        from apps.rh.models import DossierEmploye
        from apps.sav.models import Ticket
        from apps.stock.models import Fournisseur, Produit
        from apps.ventes.models import Devis

        expected = {
            'lead': Lead, 'client': Client, 'produit': Produit,
            'devis': Devis, 'installation': Installation, 'ticket': Ticket,
            'document': Document, 'fournisseur': Fournisseur,
            'employe': DossierEmploye,
        }
        for key, model in expected.items():
            self.assertIs(registry.get_model(key), model, key)

    def test_pilots_still_registered_via_central_loader(self):
        """contrat/vehicule sont toujours enregistrés — désormais via le
        chargeur central (CustomfieldsConfig.ready()), plus via les
        AppConfig.ready() de contrats/flotte."""
        from apps.contrats.models import Contrat
        from apps.flotte.models import Vehicule
        self.assertTrue(registry.is_registered('contrat'))
        self.assertTrue(registry.is_registered('vehicule'))
        self.assertIs(registry.get_model('contrat'), Contrat)
        self.assertIs(registry.get_model('vehicule'), Vehicule)


class TestSourceIsPlatformManifestNotAppReady(SimpleTestCase):
    """Preuve que la source a bien basculé vers les manifestes : ré-exécuter
    ``register_from_platform_manifests()`` seul (sans les anciens appels
    ContratsConfig/FlotteConfig.ready()) suffit à retrouver les 2 pilotes."""

    def test_central_loader_alone_registers_pilots(self):
        # On retire temporairement les entrées pour prouver qu'elles
        # reviennent bien via le chargeur central (pas un résidu d'un autre
        # ready() déjà exécuté au démarrage du process de test).
        registry.unregister('contrat')
        registry.unregister('vehicule')
        self.assertFalse(registry.is_registered('contrat'))
        self.assertFalse(registry.is_registered('vehicule'))
        try:
            registry.register_from_platform_manifests()
            self.assertTrue(registry.is_registered('contrat'))
            self.assertTrue(registry.is_registered('vehicule'))
        finally:
            # Ré-enregistre au cas où un test suivant dépendrait de l'état
            # initial (idempotent, aucun risque de conflit).
            registry.register_from_platform_manifests()

    def test_contrats_apps_ready_no_longer_calls_register_directly(self):
        """ContratsConfig.ready() n'importe plus le registre customfields —
        preuve statique que la déclaration a bien migré vers platform.py.
        (On vérifie l'IMPORT, pas la chaîne « register( » : le commentaire
        historique du ready() cite l'ancien appel à titre documentaire.)"""
        import inspect
        from apps.contrats.apps import ContratsConfig
        source = inspect.getsource(ContratsConfig.ready)
        self.assertNotIn('from apps.customfields import registry', source)

    def test_flotte_config_has_no_ready_override(self):
        """FlotteConfig n'a plus besoin de ready() du tout (plus rien à y
        enregistrer explicitement)."""
        from apps.flotte.apps import FlotteConfig
        self.assertNotIn('ready', FlotteConfig.__dict__)


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
