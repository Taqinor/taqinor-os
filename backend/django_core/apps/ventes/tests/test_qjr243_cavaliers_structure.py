# -*- coding: utf-8 -*-
"""QJR243 — lot MÉCANIQUE : cavaliers de structure + recensement des chemins
de création de lignes.

Sept points, aucun changement de nombre monétaire :

(a) ``domain/pipeline`` — trois noms importés jamais utilisés, sous un
    ``# noqa: F401`` global qui garantissait qu'aucun linter ne le dirait
    jamais. Retirés ; le ``noqa`` restreint à ``E402``.
(b) ``domain/pipeline.decider_taille`` — l'étape 2 déclarait un paramètre
    ``entrees`` qu'elle ne LISAIT pas : la chaîne documentée
    « ``resoudre_entrees`` → ``decider_taille`` » ne transportait rien.
    Paramètre retiré, documentation corrigée.
(c) ``domain/creation._arbitrage_du_calepinage`` — une lecture de wattage de
    layout avait échappé à l'unification QJR165 : elle re-parsait ``panelWatt``
    en ligne, sans normalisation ni garde d'exception. Elle passe par le
    lecteur unique.
(d) ``quote_engine/agricole/sample_data.py`` — quatrième copie de la chaîne
    monnaie : CONSTATÉ SUPPRIMÉ par QJR236 (décision DV1), rien à recréer.
(e) ``domain/etudes`` — docstring du contrat pré-QJR47, fausse des deux côtés.
(f) ``docs/PLAN2.md`` — chiffre du DONE LOG (687 vs 693 lignes) : hors
    périmètre d'un agent de lane (les fichiers de plan appartiennent à
    l'orchestrateur) ; remonté dans le rapport de lane.
(g) ``domain/lignes`` — le recensement R4-B1 se déclarait exhaustif à six
    chemins secondaires et ``creer_ligne`` « le seul endroit où naît une
    ligne » : quatre chemins de plus et deux contournements de la garde AST
    reçoivent leur verdict ÉCRIT, sans aucun recâblage.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr243_cavaliers_structure -v 2
"""
import inspect
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.domain import creation as _creation
from apps.ventes.domain import etudes as _etudes
from apps.ventes.domain import lignes as _lignes
from apps.ventes.domain import pipeline as _pipeline

VENTES = Path(__file__).resolve().parents[1]


class CavalierAImportsMorts(SimpleTestCase):

    def test_les_trois_noms_ont_disparu(self):
        for nom in ('SCENARIO_LES_DEUX', '_scenario_stocke', 'sert_les_deux'):
            with self.subTest(nom=nom):
                self.assertFalse(hasattr(_pipeline, nom))

    def test_les_deux_noms_reellement_lus_restent(self):
        for nom in ('scenario_servable', 'poser_puissance_kwc'):
            with self.subTest(nom=nom):
                self.assertTrue(hasattr(_pipeline, nom))

    def test_le_noqa_ne_couvre_plus_F401_sur_cet_import(self):
        source = (VENTES / 'domain' / 'pipeline.py').read_text(
            encoding='utf-8')
        ligne = next(li for li in source.splitlines()
                     if 'domain.scenario import' in li)
        self.assertIn('noqa: E402', ligne)
        self.assertNotIn('F401', ligne)


class CavalierBEtape2SansParametreMort(SimpleTestCase):

    def test_la_signature_ne_declare_plus_entrees(self):
        # QJR304 — ``devis`` s'est ajouté (le registre de surcharges de CE
        # devis alimente l'étape 2, R4-A phrase 2) ; ce que ce test tient,
        # c'est qu'``entrees`` — le paramètre MORT — ne revienne jamais.
        parametres = list(
            inspect.signature(_pipeline.decider_taille).parameters)
        self.assertNotIn('entrees', parametres)
        self.assertEqual(parametres[0], 'intention')

    def test_une_cible_deja_arretee_ressort_telle_quelle(self):
        """Le comportement, lui, est INCHANGÉ."""
        cible = _pipeline.CibleDevis(nb_panneaux=14, panel_watt=550, kwc=7.7)
        intention = _pipeline.IntentionDevis(
            origine=_pipeline.ORIGINE_ECRAN, company=object(), cible=cible)
        self.assertIs(_pipeline.decider_taille(intention), cible)

    def test_sans_cible_ni_lead_l_etape_rend_None(self):
        intention = _pipeline.IntentionDevis(
            origine=_pipeline.ORIGINE_ECRAN, company=object())
        self.assertIsNone(_pipeline.decider_taille(intention))

    def test_le_site_d_appel_ne_passe_plus_les_entrees(self):
        source = inspect.getsource(_pipeline.appliquer)
        # QJR304 — le site d'appel passe désormais le DEVIS (jamais les
        # entrées) : c'est son registre qui porte la cible de niveau devis.
        self.assertIn('decider_taille(intention, devis)', source)
        self.assertNotIn('decider_taille(intention, entrees)', source)


class CavalierCLectureUniqueDuWattage(SimpleTestCase):
    """L'arbitrage du calepinage passe par ``geometrie.lire_layout``."""

    def _arbitrer(self, layout, nb_panneaux, kwc, retenu):
        vrai = _creation.arbitrer_compte_calepinage
        _creation.arbitrer_compte_calepinage = (
            lambda *a, **k: {'retenu': retenu})
        self.addCleanup(
            setattr, _creation, 'arbitrer_compte_calepinage', vrai)
        return _creation._arbitrage_du_calepinage(
            layout, nb_panneaux, kwc, company=None)

    def test_un_wattage_illisible_ne_fait_plus_LEVER_la_creation(self):
        """LE ROUGE : ``float("abc")`` cassait la création de devis."""
        layout = {'panelWatt': 'abc', 'result': {'panels': 10, 'kwc': 5.5}}
        nb, kwc = self._arbitrer(layout, 10, 5.5, retenu=12)
        self.assertEqual(nb, 12)
        self.assertIsNotNone(kwc)

    def test_un_wattage_annonce_est_normalise(self):
        """545,6 W devient 546 W — la normalisation du lecteur unique, que la
        lecture en ligne n'appliquait pas."""
        layout = {'panelWatt': 545.6, 'result': {'panels': 10, 'kwc': 5.456}}
        nb, kwc = self._arbitrer(layout, 10, 5.456, retenu=12)
        self.assertEqual(nb, 12)
        self.assertAlmostEqual(kwc, round(12 * 546 / 1000.0, 3), places=3)

    def test_un_arbitrage_sans_changement_ne_touche_a_rien(self):
        layout = {'panelWatt': 550, 'result': {'panels': 10, 'kwc': 5.5}}
        self.assertEqual(self._arbitrer(layout, 10, 5.5, retenu=10), (10, 5.5))

    def test_la_lecture_en_ligne_a_disparu(self):
        source = inspect.getsource(_creation._arbitrage_du_calepinage)
        self.assertIn('lire_layout(', source)
        self.assertNotIn("layout.get('panelWatt')", source)


class CavalierDSampleDataAgricole(SimpleTestCase):
    """(d) — CONSTATER, ne pas recréer."""

    def test_le_fichier_a_bien_ete_supprime_par_qjr236(self):
        chemin = VENTES / 'quote_engine' / 'agricole' / 'sample_data.py'
        self.assertFalse(
            chemin.exists(),
            'QJR243 (d) demandait de CONSTATER la suppression QJR236, pas de '
            'recréer la quatrième copie de la chaîne monnaie.')

    def test_le_moteur_agronomique_lui_est_intact(self):
        from apps.ventes.quote_engine.agricole import agronomy

        self.assertTrue(hasattr(agronomy, 'monthly_water_demand'))
        self.assertTrue(hasattr(agronomy, 'ET0_MONTHLY'))


class CavalierEDocstringDesEtudes(SimpleTestCase):

    def test_la_docstring_ne_promet_plus_le_contrat_pre_QJR47(self):
        doc = _etudes.rafraichir_etude_horaire_devis.__doc__ or ''
        self.assertIn('QJR243', doc)
        self.assertIn('QJR47', doc)
        self.assertNotIn(
            "Les chemins « devis » (``perform_update``, ``replace-lines``)\n"
            "    peuvent en revanche", doc)

    def test_les_deux_chemins_cites_ne_forcent_effectivement_pas(self):
        """La preuve, lue sur le code : ni ``perform_update`` ni
        ``replace-lines`` ne passent ``force=True``."""
        source = (VENTES / 'views' / 'devis.py').read_text(encoding='utf-8')
        self.assertNotIn('rafraichir_etudes_du_devis(devis, force=True)',
                         source)


class CavalierGRecensementAvecVerdicts(SimpleTestCase):
    """(g) — chaque chemin a SON verdict écrit ; rien n'est recâblé."""

    def _recensement(self):
        return (VENTES / 'domain' / 'lignes.py').read_text(encoding='utf-8')

    def test_les_quatre_chemins_supplementaires_sont_nommes(self):
        source = self._recensement()
        for chemin in ('_completer_kit_residentiel',
                       'reconcilier',
                       'apply_preset_to_devis',
                       'reparer_devis_deux_options'):
            with self.subTest(chemin=chemin):
                self.assertIn(chemin, source)

    def test_les_deux_contournements_de_la_garde_sont_nommes(self):
        source = self._recensement()
        self.assertIn('LigneDevisViewSet', source)
        self.assertIn('apps/cpq/services', source)

    def test_creer_ligne_ne_se_declare_plus_le_SEUL_endroit(self):
        doc = _lignes.creer_ligne.__doc__ or ''
        self.assertIn('GOULOT PYTHON', doc)
        self.assertNotIn(
            'Le seul endroit de ``apps/ventes`` où\n    une ligne de devis '
            'naît', doc)

    def test_aucun_recablage_dans_ce_lot(self):
        """Les cinq écritures cross-app de ``cpq`` sont CONSTATÉES, pas
        déplacées : le lot ne recâble rien."""
        source = (VENTES.parent / 'cpq' / 'services.py').read_text(
            encoding='utf-8')
        self.assertNotIn('from apps.ventes.domain.lignes import creer_ligne',
                         source)
