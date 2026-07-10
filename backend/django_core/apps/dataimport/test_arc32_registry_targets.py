"""ARC32 — ``dataimport.services.TARGETS`` lit le registre plateforme.

Couvre : (1) non-régression stricte — le ``set`` résolu par la vue paresseuse
``_LazyTargets`` est EXACTEMENT identique aux 8 clés ``FIELD_MAPS`` historiques
(chaque cible étant désormais déclarée par son app propriétaire dans son
``platform.py``) ; (2) l'API existante (``in``, itération, ``len``, ``sorted``)
se comporte à l'identique (DROP-IN replacement) ; (3) chaque cible historique
est bien déclarée dans un manifeste plateforme (``import_specs``) ET conserve
son mapping d'en-têtes dans ``FIELD_MAPS`` ; (4) une nouvelle cible déclarée
UNIQUEMENT dans un manifeste fictif apparaît dans ``TARGETS`` sans toucher
``apps/dataimport/services.py`` — preuve que la résolution suit vraiment
``core.platform.import_specs()`` ; (5) les 6+2 cibles restent inchangées côté
FIELD_MAPS (idempotence de la liste des cibles).
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.dataimport.services import FIELD_MAPS, TARGETS, _LazyTargets

# Les 8 clés FIELD_MAPS historiques (set littéral d'avant ARC32) — la référence
# de non-régression. Toute divergence ici = régression réelle du registre.
HISTORICAL_TARGETS = {
    'leads', 'clients', 'products', 'fournisseurs', 'equipements',
    'vehicules', 'contrats', 'dossiers_rh',
}

# Cible → app propriétaire attendue (déclarante dans son platform.py).
TARGET_OWNER_MODULE = {
    'leads': 'crm', 'clients': 'crm',
    'products': 'stock', 'fournisseurs': 'stock',
    'equipements': 'sav',
    'vehicules': 'flotte',
    'contrats': 'contrats',
    'dossiers_rh': 'rh',
}


class TestTargetsNonRegression(SimpleTestCase):
    """Le registre résout EXACTEMENT le même ensemble que l'ancien littéral."""

    def test_resolved_set_matches_historical_literal_exactly(self):
        resolved = set(TARGETS)
        self.assertEqual(
            resolved, HISTORICAL_TARGETS,
            f"Divergence — manquants: {HISTORICAL_TARGETS - resolved}, "
            f"en trop: {resolved - HISTORICAL_TARGETS}")

    def test_len_matches(self):
        self.assertEqual(len(TARGETS), 8)

    def test_contains_works_for_each_historical_target(self):
        for cible in HISTORICAL_TARGETS:
            self.assertIn(cible, TARGETS, cible)

    def test_unknown_target_not_contained(self):
        self.assertNotIn('bidon_inexistant', TARGETS)

    def test_sorted_and_iteration_still_work(self):
        # Les vues (views.py) font ``', '.join(sorted(services.TARGETS))`` — le
        # DROP-IN doit rester itérable et triable.
        self.assertEqual(sorted(TARGETS), sorted(HISTORICAL_TARGETS))

    def test_repeated_access_is_stable(self):
        first = set(TARGETS)
        second = set(TARGETS)
        self.assertEqual(first, second)


class TestFieldMapsUnchanged(SimpleTestCase):
    """Les 6+2 cibles FIELD_MAPS (mappings d'en-têtes) restent inchangées : le
    registre ne remplace PAS les mappings, il unionne seulement la LISTE."""

    def test_field_maps_keys_are_the_eight_targets(self):
        self.assertEqual(set(FIELD_MAPS), HISTORICAL_TARGETS)

    def test_every_target_keeps_a_header_mapping(self):
        for cible in HISTORICAL_TARGETS:
            self.assertIn(cible, FIELD_MAPS, cible)
            self.assertTrue(FIELD_MAPS[cible], cible)


class TestTargetsDeclaredByOwnerManifests(SimpleTestCase):
    """Chaque cible historique est DÉCLARÉE dans le manifeste plateforme de son
    app propriétaire (surface ``import_specs``) — la source de vérité répartie."""

    def test_each_target_declared_in_its_owner_manifest(self):
        from core import platform

        manifests = platform.collect_platform_manifests()
        for cible, owner in TARGET_OWNER_MODULE.items():
            self.assertIn(owner, manifests, owner)
            self.assertIn(
                cible, manifests[owner]['import_specs'],
                f"{cible} devrait être déclaré dans apps/{owner}/platform.py")

    def test_registry_import_specs_covers_all_targets(self):
        from core import platform

        declares = platform.import_specs(company=None)
        self.assertTrue(
            HISTORICAL_TARGETS.issubset(declares),
            f"Cibles non déclarées au registre : "
            f"{HISTORICAL_TARGETS - set(declares)}")


class TestNewManifestTargetAppearsWithoutTouchingServices(SimpleTestCase):
    """Une cible déclarée UNIQUEMENT via un manifeste fictif (jamais en modifiant
    apps/dataimport/services.py) apparaît dans TARGETS — preuve que la résolution
    suit vraiment core.platform.import_specs()."""

    def test_fictitious_manifest_target_is_picked_up(self):
        from core import platform as core_platform

        vrais = core_platform.collect_platform_manifests()
        faux = dict(vrais)
        faux['bidon_arc32'] = {
            'module': 'bidon_arc32',
            'record_targets': [], 'searchable_models': [],
            'customfield_models': [], 'import_specs': ['machin_arc32'],
            'agent_actions_module': '', 'automation_state_fields': [],
            'kpi_providers': [],
        }

        with mock.patch(
                'core.platform.collect_platform_manifests',
                side_effect=lambda: faux):
            resolved = _LazyTargets()._resolve()
        self.assertIn('machin_arc32', resolved)
        # Les 8 cibles historiques restent présentes (union, pas remplacement).
        self.assertTrue(HISTORICAL_TARGETS.issubset(resolved))

    def test_export_registry_bridge_reads_declared_import_specs(self):
        from apps.dataimport.export_registry import declared_import_specs

        declared = declared_import_specs()
        self.assertTrue(
            HISTORICAL_TARGETS.issubset(declared),
            f"Bridge export incomplet : {HISTORICAL_TARGETS - declared}")
