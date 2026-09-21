"""ARC32 — ``dataimport.services.TARGETS`` lit le registre plateforme.

Couvre : (1) non-régression stricte — le ``set`` résolu par la vue paresseuse
``_LazyTargets`` est EXACTEMENT identique à la référence figée
``EXPECTED_TARGETS`` (les cibles ``FIELD_MAPS`` GARDÉES + les cibles ajoutées
DÉLIBÉRÉMENT depuis, chacune nommée : ``HISTORICAL_TARGETS`` pour celles que
dataimport lit lui-même, ``REGISTRY_ONLY_TARGETS`` pour celles dont l'app
propriétaire porte son propre lecteur — ou n'a plus de lecteur dataimport du
tout, cf. SOLMVP20 ci-dessous), chaque cible étant déclarée par son app
propriétaire dans son ``platform.py`` ; (2) l'API existante (``in``, itération, ``len``, ``sorted``)
se comporte à l'identique (DROP-IN replacement) ; (3) chaque cible historique
est bien déclarée dans un manifeste plateforme (``import_specs``) ET conserve
son mapping d'en-têtes dans ``FIELD_MAPS`` (les cibles à lecteur propre, elles,
restent DEHORS de ``FIELD_MAPS`` — vérifié) ; (4) une nouvelle cible déclarée
UNIQUEMENT dans un manifeste fictif apparaît dans ``TARGETS`` sans toucher
``apps/dataimport/services.py`` — preuve que la résolution suit vraiment
``core.platform.import_specs()`` ; (5) les cibles FIELD_MAPS restent
inchangées (idempotence de la liste des cibles).
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.dataimport.services import FIELD_MAPS, TARGETS, _LazyTargets

# Les clés FIELD_MAPS GARDÉES (dataimport lit lui-même leur mapping
# d'en-têtes) + toute cible ajoutée DÉLIBÉRÉMENT depuis, chacune nommée par sa
# tâche — la référence de non-régression. Toute divergence ici = régression
# réelle du registre (une cible qui DISPARAÎT, ou une cible ajoutée sans être
# déclarée ici).
#
#   NTMIG10 — 'devis'/'factures' : import d'EN-TÊTES (lignes via NTMIG11, un
#   second fichier) pour les migrations sortantes (kits Odoo/Sage NTMIG8/12),
#   déclarées par ``apps/ventes/platform.py`` (``import_specs``), mapping
#   d'en-têtes dans ``dataimport.FIELD_MAPS``, écriture DÉLÉGUÉE à
#   ``apps.ventes.services.creer_devis_import``/``creer_facture_import``
#   (mode `creer` uniquement — pas dans ``UPSERT_TARGETS``).
HISTORICAL_TARGETS = {
    'leads', 'clients', 'products', 'fournisseurs', 'equipements',
    'devis', 'factures',
}

# Cibles déclarées au registre par une app qui porte son PROPRE lecteur de
# fichier (donc SANS entrée dans ``dataimport.FIELD_MAPS``), OU dont le
# mapping/l'écriture dataimport a été retiré côté SOLMVP20 alors que l'app
# propriétaire elle-même n'est pas encore coquillée. Elles apparaissent
# légitimement dans ``TARGETS`` (l'union paresseuse) mais pas dans les mappings
# d'en-têtes de dataimport : les deux ensembles ne coïncident plus, et c'est le
# comportement voulu du registre réparti.
#
# SOLMVP-sweep (2026-09-21) — vide aujourd'hui. Chaque cible qui vivait ici
# (AOF30/AOF165/AOF169 'obstacles'/'chaines'/'avis' via apps/ao ; VAO28
# 'avis_veille' via apps/veille_ao ; SOLMVP20 'vehicules'/'contrats'/
# 'dossiers_rh'/'eleves_education'/'scm_evenement_demande' via flotte/
# contrats/rh/education/scm) appartenait à une app QUI EST DÉSORMAIS PARQUÉE
# (Groupe SOLMVP, MVP solaire) — exactement la disparition « à ce moment-là »
# que la note SOLMVP20 anticipait déjà pour son propre groupe. Une app
# parquée n'a plus de ``platform.py`` du tout, donc plus aucune de ces cibles
# ne résout via le registre (vérifié en shell Django : ``TARGETS`` == les 7
# ``HISTORICAL_TARGETS`` ci-dessus, rien de plus). Laissé en ``set()`` plutôt
# que supprimé : la prochaine cible à lecteur propre d'une app KEPT le
# retrouve prêt à l'emploi, sans redécouvrir le motif.
REGISTRY_ONLY_TARGETS = set()

# Référence de non-régression du set RÉSOLU par ``_LazyTargets`` : les cibles
# FIELD_MAPS de dataimport ∪ les cibles déclarées par une app à lecteur propre.
EXPECTED_TARGETS = HISTORICAL_TARGETS | REGISTRY_ONLY_TARGETS

# Cible → app propriétaire attendue (déclarante dans son platform.py).
# SOLMVP-sweep (2026-09-21) — les entrées REGISTRY_ONLY_TARGETS (flotte/
# contrats/rh/education/scm/ao/veille_ao) sont retirées : ces apps sont
# parquées, leur ``platform.py`` a disparu avec elles (cf. REGISTRY_ONLY_
# TARGETS ci-dessus).
TARGET_OWNER_MODULE = {
    'leads': 'crm', 'clients': 'crm',
    'products': 'stock', 'fournisseurs': 'stock',
    'equipements': 'sav',
    'devis': 'ventes', 'factures': 'ventes',
}


class TestTargetsNonRegression(SimpleTestCase):
    """Le registre résout EXACTEMENT le même ensemble que l'ancien littéral."""

    def test_resolved_set_matches_historical_literal_exactly(self):
        resolved = set(TARGETS)
        self.assertEqual(
            resolved, EXPECTED_TARGETS,
            f"Divergence — manquants: {EXPECTED_TARGETS - resolved}, "
            f"en trop: {resolved - EXPECTED_TARGETS}")

    def test_len_matches(self):
        self.assertEqual(len(TARGETS), len(EXPECTED_TARGETS))

    def test_contains_works_for_each_historical_target(self):
        for cible in EXPECTED_TARGETS:
            self.assertIn(cible, TARGETS, cible)

    def test_unknown_target_not_contained(self):
        self.assertNotIn('bidon_inexistant', TARGETS)

    def test_sorted_and_iteration_still_work(self):
        # Les vues (views.py) font ``', '.join(sorted(services.TARGETS))`` — le
        # DROP-IN doit rester itérable et triable.
        self.assertEqual(sorted(TARGETS), sorted(EXPECTED_TARGETS))

    def test_repeated_access_is_stable(self):
        first = set(TARGETS)
        second = set(TARGETS)
        self.assertEqual(first, second)


class TestFieldMapsUnchanged(SimpleTestCase):
    """Les cibles FIELD_MAPS GARDÉES (mappings d'en-têtes) restent inchangées :
    le registre ne remplace PAS les mappings, il unionne seulement la LISTE."""

    def test_field_maps_keys_are_the_historical_targets(self):
        self.assertEqual(set(FIELD_MAPS), HISTORICAL_TARGETS)

    def test_every_target_keeps_a_header_mapping(self):
        for cible in HISTORICAL_TARGETS:
            self.assertIn(cible, FIELD_MAPS, cible)
            self.assertTrue(FIELD_MAPS[cible], cible)

    def test_registry_only_targets_stay_out_of_field_maps(self):
        """Une cible à lecteur propre ne se glisse pas dans ``FIELD_MAPS``.

        Le cliquet reste serré dans les DEUX sens : si l'une de ces cibles
        gagnait un mapping dataimport, elle appartiendrait à
        ``HISTORICAL_TARGETS`` et devrait y être nommée."""
        intruses = REGISTRY_ONLY_TARGETS & set(FIELD_MAPS)
        self.assertEqual(
            intruses, set(),
            f"Ces cibles ont désormais un mapping dataimport : {intruses} — "
            "déplacez-les dans HISTORICAL_TARGETS.")


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
            EXPECTED_TARGETS.issubset(declares),
            f"Cibles non déclarées au registre : "
            f"{EXPECTED_TARGETS - set(declares)}")


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
        # Les cibles attendues restent présentes (union, pas remplacement).
        self.assertTrue(EXPECTED_TARGETS.issubset(resolved))

    def test_export_registry_bridge_reads_declared_import_specs(self):
        from apps.dataimport.export_registry import declared_import_specs

        declared = declared_import_specs()
        self.assertTrue(
            EXPECTED_TARGETS.issubset(declared),
            f"Bridge export incomplet : {EXPECTED_TARGETS - declared}")
