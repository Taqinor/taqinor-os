"""ARC30 — ``records.ALLOWED_TARGETS`` lit le registre plateforme (core.platform).

Couvre : (1) non-régression stricte — le ``set`` résolu par la vue paresseuse
``_LazyAllowedTargets`` est EXACTEMENT identique aux couples historiques
littéraux (19 + les pilotes du kit ``core.documents`` : SCA34
``installations.ordresoustraitance``, SCA36 ``installations.demandeachat``) ;
(2) l'API existante (``in``, itération,
``resolve_target``) se comporte à l'identique (DROP-IN replacement) ; (3) une
nouvelle cible déclarée UNIQUEMENT dans un manifeste fictif apparaît dans
``ALLOWED_TARGETS`` sans toucher ``apps/records/models.py``.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.records.models import ALLOWED_TARGETS
from apps.records.serializers import resolve_target
from authentication.models import Company

# Les 19 couples historiques (set littéral d'avant ARC30) + les pilotes du kit
# core.documents (installations.ordresoustraitance SCA34,
# installations.demandeachat SCA36) — la référence de non-régression. Toute
# divergence ici = régression réelle du registre.
HISTORICAL_TARGETS = {
    ('crm', 'lead'),
    ('crm', 'client'),
    ('ventes', 'devis'),
    ('ventes', 'boncommande'),
    # ODX17 — Facture déplacée vers l'app ``facturation`` (state-only).
    ('facturation', 'facture'),
    ('installations', 'installation'),
    ('sav', 'ticket'),
    ('outillage', 'outillage'),
    ('stock', 'produit'),
    ('stock', 'fournisseur'),
    ('rh', 'dossieremploye'),
    ('qhse', 'relevecontrole'),
    ('qhse', 'nonconformite'),
    ('kb', 'kbarticle'),
    ('ged', 'document'),
    ('contrats', 'contrat'),
    ('flotte', 'vehicule'),
    ('gestion_projet', 'projet'),
    ('ao', 'appeloffre'),
    # SCA34 — pilote 1 du kit core.documents (chatter câblé sur son viewset).
    ('installations', 'ordresoustraitance'),
    # SCA36 — pilote 3 du kit core.documents (dégradation gracieuse sans
    # totaux ; chatter câblé sur son viewset).
    ('installations', 'demandeachat'),
    # NTCON — vertical BTP/Chantier : pièces jointes photos via
    # ``records.Attachment`` (déclarées dans ``apps/btp_chantier/platform.py``).
    ('btp_chantier', 'reservechantier'),
    ('btp_chantier', 'journalchantier'),
    ('btp_chantier', 'rfireponse'),
    # NTIDE1 — boîte à idées : l'historique/tags d'une idée passe par le
    # chatter/tag générique records (ARC8/FG9), pas un modèle *Activity maison.
    ('innovation', 'idee'),
}


class TestAllowedTargetsNonRegression(SimpleTestCase):
    """Le registre résout EXACTEMENT le même ensemble que l'ancien littéral."""

    def test_resolved_set_matches_historical_literal_exactly(self):
        resolved = set(ALLOWED_TARGETS)
        self.assertEqual(
            resolved, HISTORICAL_TARGETS,
            f"Divergence — manquants: {HISTORICAL_TARGETS - resolved}, "
            f"en trop: {resolved - HISTORICAL_TARGETS}")

    def test_len_matches(self):
        self.assertEqual(len(ALLOWED_TARGETS), 25)

    def test_contains_works_for_each_historical_pair(self):
        for pair in HISTORICAL_TARGETS:
            self.assertIn(pair, ALLOWED_TARGETS, pair)

    def test_unknown_pair_not_contained(self):
        self.assertNotIn(('bidon', 'inexistant'), ALLOWED_TARGETS)

    def test_repeated_access_is_stable(self):
        """Deux résolutions successives donnent le même résultat (pas d'effet
        de bord / pas de dérive entre appels)."""
        first = set(ALLOWED_TARGETS)
        second = set(ALLOWED_TARGETS)
        self.assertEqual(first, second)


class TestResolveTargetStillWorks(TestCase):
    """``resolve_target`` (records/serializers.py) — DROP-IN non-régression :
    le comportement existant (accepte les cibles connues, société scopée)
    reste identique après le passage au registre paresseux."""

    def setUp(self):
        self.company = Company.objects.create(nom='ARC30 Registry Co')

    def test_resolve_target_accepts_known_pair(self):
        from apps.crm.models import Lead
        lead = Lead.objects.create(company=self.company, nom='ARC30 Lead')
        ct, resolved = resolve_target('crm.lead', lead.pk, self.company)
        self.assertEqual(resolved.pk, lead.pk)

    def test_resolve_target_rejects_unknown_pair(self):
        with self.assertRaises(ValueError):
            resolve_target('bidon.inexistant', 1, self.company)


class TestNewManifestTargetAppearsWithoutTouchingRecordsModels(SimpleTestCase):
    """Une cible déclarée UNIQUEMENT via un manifeste fictif (jamais en
    modifiant apps/records/models.py) apparaît dans ALLOWED_TARGETS — preuve
    que la résolution suit vraiment core.platform.record_targets()."""

    def test_fictitious_manifest_target_is_picked_up(self):
        from core import platform as core_platform

        vrais = core_platform.collect_platform_manifests()
        faux = dict(vrais)
        faux['bidon_arc30'] = {
            'module': 'bidon_arc30',
            'record_targets': ['bidon.machin_arc30'],
            'searchable_models': [], 'customfield_models': [],
            'import_specs': [], 'agent_actions_module': '',
            'automation_state_fields': [], 'kpi_providers': [],
        }

        def _fake_collect():
            return faux

        with mock.patch(
                'core.platform.collect_platform_manifests',
                side_effect=_fake_collect):
            resolved = ALLOWED_TARGETS._resolve()
        self.assertIn(('bidon', 'machin_arc30'), resolved)
        # Les 19 cibles historiques restent aussi présentes (union, pas remplacement).
        self.assertTrue(HISTORICAL_TARGETS.issubset(resolved))
