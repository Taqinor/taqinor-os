"""ARC30 — ``records.ALLOWED_TARGETS`` lit le registre plateforme (core.platform).

Couvre : (1) non-régression stricte — le ``set`` résolu par la vue paresseuse
``_LazyAllowedTargets`` est EXACTEMENT identique aux couples historiques
littéraux ; (2) l'API existante (``in``, itération,
``resolve_target``) se comporte à l'identique (DROP-IN replacement) ; (3) une
nouvelle cible déclarée UNIQUEMENT dans un manifeste fictif apparaît dans
``ALLOWED_TARGETS`` sans toucher ``apps/records/models.py``.

SOLMVP (2026-09-21) — le registre plateforme est GÉNÉRIQUE (``core.platform``
scanne ``apps/<x>/platform.py``) : les 47 apps parquées (Groupe SOLMVP, MVP
solaire) ont perdu leur ``platform.py`` avec le reste de leur code, donc
toutes leurs cibles ``record_targets`` ont disparu de la résolution SANS
qu'aucune ligne d'ici n'ait besoin d'être touchée à la main — sauf la
référence de non-régression ci-dessous, qui doit suivre la RÉALITÉ. Deux
cibles ``installations`` (``ordresoustraitance`` SCA34, ``rfq`` NTP2P44) sont
également retirées : SOLMVP13 a désinscrit leurs sous-fonctions (écrans +
endpoints, modèles conservés) d'``apps/installations/platform.py`` — le
chatter qu'elles ciblaient n'a donc plus de site d'appel. Vérifié en direct
(``ALLOWED_TARGETS`` en shell Django) : 15 couples résolvent aujourd'hui.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.records.models import ALLOWED_TARGETS
from apps.records.serializers import resolve_target
from authentication.models import Company

# Référence de non-régression : les couples RÉELLEMENT résolus aujourd'hui.
# Toute divergence ici = régression réelle du registre.
#
# SOLMVP (2026-09-21) — retirés d'ici (plus déclarés par aucun
# ``platform.py``, vérifié en shell Django) : les cibles des 47 apps
# parquées qui portaient un manifeste (rh.dossieremploye, qhse.relevecontrole,
# qhse.nonconformite, kb.kbarticle, contrats.contrat, flotte.vehicule,
# gestion_projet.projet, ao.appeloffre, btp_chantier.* [reservechantier,
# journalchantier, rfireponse, rfi, visadocument, avenantchantier,
# decomptegeneral], innovation.idee, assurances.* [declarationsinistre,
# policeassurance, attestationassurance], credit.* [limitecredit,
# derogationcredit], esg.documentpolitiqueesg, veille_ao.avismarche,
# transport.* [ordretransport, etapetransport, reservereception],
# douane.dossierexport, mrp.ordrefabrication) ; ET les deux pilotes
# ``installations`` dont SOLMVP13 a désinscrit la sous-fonction
# d'``apps/installations/platform.py`` (écrans + endpoints retirés, modèles
# conservés) : ``installations.ordresoustraitance`` (SCA34) et
# ``installations.rfq`` (NTP2P44).
HISTORICAL_TARGETS = {
    ('crm', 'lead'),
    ('crm', 'client'),
    ('ventes', 'devis'),
    ('ventes', 'boncommande'),
    # ODX17 — Facture déplacée vers l'app ``facturation`` (state-only).
    ('facturation', 'facture'),
    # PV45 — le dossier réglementaire reçoit le schéma unifilaire en pièce
    # jointe (records.Attachment, jamais un FileField — ARC26).
    ('ventes', 'regulatorydossier'),
    ('installations', 'installation'),
    ('sav', 'ticket'),
    ('outillage', 'outillage'),
    ('stock', 'produit'),
    ('stock', 'fournisseur'),
    ('ged', 'document'),
    # SCA36 — pilote 3 du kit core.documents (dégradation gracieuse sans
    # totaux ; chatter câblé sur son viewset).
    ('installations', 'demandeachat'),
    # NTADM47 — l'entité (hiérarchie intra-tenant) journalise ses transitions
    # (renommage/re-parentage) via le chatter générique records (ARC8), ciblée
    # par ``apps/entites/platform.py``.
    ('entites', 'entite'),
    # CAL26 — chatter GÉNÉRIQUE (journal ancien→nouveau + notes manuelles) sur
    # le calepinage, ciblé par ``apps/calepinage/platform.py``
    # (``record_targets``). Le module n'a qu'UN objet chatté : la conception.
    ('calepinage', 'calepinage'),
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
        # SOLMVP (2026-09-21) — 15 couples résolvent aujourd'hui (47 apps
        # parquées + 2 sous-fonctions installations désinscrites : voir le
        # commentaire de HISTORICAL_TARGETS ci-dessus pour le détail).
        self.assertEqual(len(ALLOWED_TARGETS), 15)

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
